"""
Pre-hook and post-hook guardrails implementation for the ECLA AI Customer Support Agent.
Includes content filtering and history summarization.
"""

import logging
from typing import Dict, Any

import openai
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage

from src.config.settings import settings

# Set up logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client for moderation
openai.api_key = settings.openai_api_key

# Initialize summarizer model
summarizer_model = init_chat_model(
    model="gpt-4o-mini",
    model_provider="openai",
    temperature=0.1,
    max_tokens=500,
    api_key=settings.openai_api_key,
)

# Define the maximum number of messages to keep in history before summarizing
MAX_HISTORY_LENGTH = 10

class ContentModerationError(Exception):
    """Exception raised when content is flagged by moderation."""
    pass

def is_harmful_content(text: str) -> Dict[str, Any]:
    """
    Use OpenAI Moderation API to check for harmful content.
    
    Args:
        text: Text to moderate
        
    Returns:
        Dictionary with moderation results
    """
    try:
        response = openai.moderations.create(input=text)
        result = response.results[0]
        
        moderation_result = {
            'flagged': result.flagged,
            'categories': result.categories.model_dump() if result.categories else {},
            'category_scores': result.category_scores.model_dump() if result.category_scores else {},
        }
        
        logger.info(f"Content moderation completed. Flagged: {result.flagged}")
        return moderation_result
        
    except Exception as e:
        logger.error(f"Content moderation failed: {e}")
        # In case of API failure, err on the side of caution and don't flag
        return {
            'flagged': False,
            'categories': {},
            'category_scores': {},
            'error': str(e)
        }

def curse_word_guardrail_hook(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pre-hook guardrail that blocks harmful content using OpenAI's Moderation API.
    
    Args:
        state: Current conversation state
        
    Returns:
        Updated state, potentially with a rejection message if content is flagged.
    """
    try:
        messages = state.get('messages', [])
        
        if not messages:
            logger.warning("No messages in state for content filtering")
            return state
        
        last_message = messages[-1]
        
        if not hasattr(last_message, 'content') or not last_message.content:
            logger.warning("Last message has no content for moderation")
            return state
        
        message_content = last_message.content
        
        moderation_result = is_harmful_content(message_content)
        
        if moderation_result.get('flagged', False):
            logger.warning(f"Content flagged by moderation: {moderation_result.get('categories', {})}")
            
            # Block the harmful message and return a rejection message
            rejection_message = SystemMessage(
                content="I cannot process requests that violate our safety policies. Please rephrase your message."
            )
            
            # Replace the last message with the rejection message
            return {
                'messages': messages[:-1] + [rejection_message],
                'moderation_flagged': True,
                'moderation_categories': moderation_result.get('categories', {})
            }
        
        logger.info("Content passed moderation check.")
        return state
        
    except Exception as e:
        logger.error(f"Curse word guardrail hook failed: {e}")
        # In case of an unexpected error, allow the message to pass but log the failure
        return {
            **state,
            'guardrail_error': str(e)
        }

def history_summarizer_hook(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pre-hook to summarize conversation history if it exceeds a certain length.
    
    Args:
        state: Current conversation state
        
    Returns:
        Updated state with summarized history if applicable
    """
    try:
        messages = state.get('messages', [])
        
        if len(messages) > MAX_HISTORY_LENGTH:
            logger.info(f"History length ({len(messages)}) exceeds max ({MAX_HISTORY_LENGTH}). Summarizing.")
            
            # Create the summarization prompt
            summarization_prompt = [
                SystemMessage(
                    content="You are a conversation summarizer. Distill the following chat history into a concise summary. "
                            "Focus on key facts, user intents, and important product details mentioned. "
                            "This summary will be used as context for an AI agent."
                ),
                *messages
            ]
            
            # Summarize the conversation
            summary_message = summarizer_model.invoke(summarization_prompt)
            
            # Keep the last user message and prepend the summary
            last_user_message = messages[-1]
            
            # Create a new state with the summary and the last message
            new_messages = [
                SystemMessage(content=f"Conversation Summary:\n{summary_message.content}"),
                last_user_message
            ]
            
            logger.info(f"History summarized. New message count: {len(new_messages)}")
            
            return {
                'messages': new_messages,
                'history_summarized': True,
                'original_message_count': len(messages)
            }
        
        logger.info(f"History length ({len(messages)}) is within limit. No summarization needed.")
        return state
        
    except Exception as e:
        logger.error(f"History summarizer hook failed: {e}")
        # In case of error, return original state to avoid breaking the conversation
        return {
            **state,
            'summarizer_error': str(e)
        } 