"""
Context-Augmented Generation (CAG) tool for the ECLA AI Agent.
This tool uses a large language model with a comprehensive, hardcoded context
of all ECLA product and company information to answer user queries,
bypassing the need for a traditional RAG vector store.
"""

import logging
from typing import Dict, Any

from langchain.tools import tool
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.config.settings import settings
from src.data.knowledge_base import ECLA_KNOWLEDGE_BASE

# --- Helper function to format the knowledge base into a single string ---
def _format_ecla_knowledge_to_string(kb: Dict[str, Any]) -> str:
    """Converts the ECLA knowledge base dictionary into a single formatted string."""
    full_text = []

    # Format Products
    full_text.append("## ECLA Products")
    for product_info in kb["products"].values():
        features = '\n'.join([f"- {feature}" for feature in product_info['features']])
        product_text = (
            f"### {product_info['name']} - Price: {product_info['price']}\n"
            f"**Description**: {product_info['description']}\n"
            f"**Features**:\n{features}\n"
            f"**Usage**: {product_info['usage']}"
        )
        full_text.append(product_text)

    # Format Company Info
    company_info = kb["company_info"]
    full_text.append("\n## Company Information")
    company_text = (
        f"- **Name**: {company_info['name']}\n"
        f"- **Website**: {company_info['website']}\n"
        f"- **Contact**: Phone: {company_info['phone']}, Email: {company_info['email']}\n"
        f"- **Address**: {company_info['address']}\n"
        f"- **About**: {company_info['description']}\n"
        f"- **Offer**: {company_info['special_offers']}"
    )
    full_text.append(company_text)

    # Format Safety Info
    safety_info = kb["safety_information"]
    full_text.append("\n## Safety Information")
    safety_text = (
        f"- **General**: {safety_info['general_safety']}\n"
        f"- **Age Limit**: {safety_info['age_restrictions']}\n"
        f"- **Side Effects**: {safety_info['side_effects']}"
    )
    full_text.append(safety_text)

    # Format FAQs
    full_text.append("\n## Frequently Asked Questions (FAQ)")
    for question, answer in kb["faq"].items():
        q_text = ' '.join(word.capitalize() for word in question.split('_'))
        full_text.append(f"- **Q: {q_text}?**\n  A: {answer}")

    return "\n".join(full_text)

# --- Constants for the Tool ---
ECLA_CONTEXT_STRING = _format_ecla_knowledge_to_string(ECLA_KNOWLEDGE_BASE)

SYSTEM_PROMPT = f"""
You are an expert ECLA Customer Support Agent. Your ONLY task is to answer the user's question based *exclusively* on the ECLA company and product information provided below.

You must not use any other knowledge. If the answer cannot be found in the provided context, you must clearly state that you do not have that specific information and provide the general company contact details.

--- ECLA KNOWLEDGE BASE START ---

{ECLA_CONTEXT_STRING}

--- ECLA KNOWLEDGE BASE END ---

Now, answer the following user's question based *only* on the information above.
"""

# --- Pydantic Input Schema ---
class CAGInput(BaseModel):
    query: str = Field(description="The user's question about ECLA products, usage, pricing, or company information.")

# --- Tool Implementation ---
@tool("ecla_info_tool", args_schema=CAGInput)
def context_augmented_generation_tool(query: str) -> str:
    """
    Answers questions about ECLA products, usage, pricing, and company information.
    Use this as the primary tool for any specific informational queries.
    """
    logging.info(f"CAG Tool invoked with query: {query}")
    try:
        # Initialize the fast, large-context model for this specific task
        llm = init_chat_model(
            model="gpt-4.1-nano",
            model_provider="openai",  # Set to 0 for factual, deterministic answers
            max_tokens=None,
            api_key=settings.openai_api_key,
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=query),
        ]

        # Get the answer from the LLM
        response = llm.invoke(messages)
        answer = response.content.strip()

        logging.info(f"CAG Tool generated answer: {answer}")
        return answer

    except Exception as e:
        logging.error(f"Error in CAG tool: {e}", exc_info=True)
        return "I'm sorry, but I encountered an error while trying to find that information. Please try again later." 