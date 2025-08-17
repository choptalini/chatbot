"""
Asynchronous Analytics Task Processor for SwiftReplies.ai
"""

import logging
from typing import List, Dict, Any, Optional

from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from pydantic import BaseModel, Field


from src.config.settings import settings
from src.multi_tenant_database import db  # Assuming db is thread-safe or we create new connections

logger = logging.getLogger(__name__)

# --- Pydantic Models for Structured Output ---

class ProductInterest(BaseModel):
    """Model to represent interest in a single product."""
    product_name: str = Field(..., description="The name of the product the user is interested in.")
    interest_score: float = Field(..., description="A score from 0.0 to 1.0 representing the user's level of interest.")

class AnalyticsOutput(BaseModel):
    """
    Defines the structured output for the analytics LLM call.
    """
    lead_temperature: str = Field(..., description="The lead's readiness to buy, categorized as 'Cold', 'Warm', or 'Hot'.")
    top_inquiry_topics: List[str] = Field(..., description="A list of the main topics or keywords the user asked about.")
    csat_score: Optional[int] = Field(None, description="The customer satisfaction score (1-5) if provided, never mark as null, if score is low mark as 1.")
    product_interest: List[ProductInterest] = Field([], description="A list of products the user showed interest in and their corresponding interest scores.")
    # Business impact metrics will be calculated from database values, but an LLM can provide flags
    is_potential_conversion: bool = Field(..., description="True if the conversation indicates a high likelihood of converting to a sale.")
    is_resolved_by_ai: bool = Field(..., description="True if the AI fully addressed the user's query without needing human help.")

# --- Analytics Processor ---

class AnalyticsProcessor:
    """
    A class to handle the processing of conversation analytics.
    """

    def __init__(self):
        try:
            self.analytics_model = init_chat_model(
                model="gpt-4.1-nano",
                model_provider="openai",
                # Some OpenAI models only support default temperature; omit to use model default
                max_tokens=None,
                api_key=settings.openai_api_key,
            ).with_structured_output(AnalyticsOutput)
            logger.info("Analytics model (gpt-4.1-nano) initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize analytics model: {e}", exc_info=True)
            self.analytics_model = None

    def _format_conversation_history(self, messages: List[BaseMessage]) -> str:
        """Formats the conversation history into a simple string."""
        history: List[str] = []
        for msg in messages:
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            history.append(f"{role}: {msg.content}")
        text = "\n".join(history)
        # Safeguard: keep prompt within a reasonable character budget to avoid model length errors
        max_chars = 8000
        if len(text) > max_chars:
            text = text[-max_chars:]
        return text

    async def run_analytics_task(self, state: dict):
        """
        The main asynchronous method to run the analytics task.
        This is designed to be called as a 'fire-and-forget' background task.
        """
        if not self.analytics_model:
            logger.error("Analytics model is not available. Aborting analytics task.")
            return

        try:
            thread_id = state.get('conversation_id')
            contact_id = state.get('contact_id') # We will need to ensure this is in the state
            messages = state.get('messages', [])

            if not all([thread_id, contact_id, messages]):
                logger.warning(f"Missing necessary data for analytics in state for thread_id: {thread_id}. Aborting.")
                return

            logger.info(f"Running analytics task for thread_id: {thread_id}, contact_id: {contact_id}")

            conversation_history_str = self._format_conversation_history(messages)

            prompt = [
                SystemMessage(
                    content=(
                        "You are an expert conversation analyst for an e-commerce brand. "
                        "Your task is to analyze the following conversation and extract key analytics metrics. "
                        "Focus on lead quality, customer intent, and overall satisfaction. "
                        "Provide your analysis in the requested JSON format."
                    )
                ),
                HumanMessage(
                    content=f"Here is the conversation history:\n\n{conversation_history_str}"
                )
            ]

            # Run the LLM call to get structured analytics data
            analytics_result = await self.analytics_model.ainvoke(prompt)

            if analytics_result:
                # Save the analytics data to the database
                # This function will need to be created in the database module
                success = await db.async_update_contact_analytics(contact_id, analytics_result.dict())
                if success:
                    logger.info(f"Successfully saved analytics for contact_id: {contact_id}")
                else:
                    logger.error(f"Failed to save analytics for contact_id: {contact_id}")
            else:
                logger.warning(f"Analytics model returned no result for contact_id: {contact_id}")

        except Exception as e:
            logger.error(f"Error during analytics task for contact_id {state.get('contact_id')}: {e}", exc_info=True)

# Create a singleton instance of the processor to be imported elsewhere
analytics_processor = AnalyticsProcessor()
