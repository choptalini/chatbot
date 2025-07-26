"""
Core agent implementation for the ECLA AI Customer Support Agent.
Uses LangGraph's create_react_agent with GPT-4o-mini and MemorySaver for persistence.
"""

import os
import uuid
import logging
from typing import Dict, List, Any, Optional, Annotated, Sequence
from datetime import datetime
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent
from src.config.pg_checkpoint import checkpointer as postgres_checkpointer
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages
from langchain_core.prompts import ChatPromptTemplate

# Load environment variables
load_dotenv()

from src.config.settings import settings
from src.agent.hooks import (
    curse_word_guardrail_hook,
    history_summarizer_hook,
)
from src.config.agent_configs import TOOL_REGISTRY, AGENT_CONFIGURATIONS


# Set up logging
logger = logging.getLogger(__name__)


class ECLAAgentState(MessagesState):
    """
    Extended state for the ECLA agent with additional metadata.
    Inherits from MessagesState for message handling.
    """
    # Additional state fields can be added here
    conversation_id: str
    user_id: Optional[str] = None
    language: str = "en"
    conversation_start_time: Optional[datetime] = None


class ECLAAgent:
    """
    Main ECLA AI Customer Support Agent class.
    Implements a ReAct agent using LangGraph's create_react_agent with integrated guardrails.
    """
    
    def __init__(self, agent_config: Dict[str, Any]):
        """
        Initialize the ECLA agent with a dynamic configuration.
        
        Args:
            agent_config: A dictionary containing the agent's configuration.
        """
        self.config = agent_config
        self.system_prompt = self.config["system_prompt"]
        
        # Initialize components from config
        self.model = self._initialize_model()
        self.tools = self._initialize_tools()
        self.checkpointer = self._initialize_checkpointer()
        self.agent = self._create_agent()
        
        # Hook configuration
        self.enable_pre_hooks = True
        
        logger.info(f"Agent '{self.config.get('description', 'Unnamed Agent')}' initialized successfully.")
    
    def _initialize_model(self):
        """Initialize the chat model based on the agent's configuration."""
        try:
            model_settings = self.config["model_settings"]
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key or api_key == 'your-openai-api-key-here':
                raise ValueError("OpenAI API key not found or not set properly")
            
            model = init_chat_model(
                model=model_settings.get("name", "gpt-4.1-mini"),
                model_provider=model_settings.get("provider", "openai"),
                temperature=model_settings.get("temperature", 0.1),
                max_tokens=model_settings.get("max_tokens", 1000),
                api_key=api_key,
            )
            
            logger.info(f"Model initialized: {model_settings.get('name')} with temperature={model_settings.get('temperature')}")
            return model
            
        except Exception as e:
            logger.error(f"Failed to initialize model: {e}")
            raise
    
    def _initialize_tools(self) -> List[Any]:
        """Initialize the tools for the agent based on the configuration."""
        tool_names = self.config.get("tools", [])
        tools = [TOOL_REGISTRY[name] for name in tool_names if name in TOOL_REGISTRY]
        
        logger.info(f"Initialized {len(tools)} tools: {[tool.name for tool in tools]}")
        return tools
    
    def _initialize_checkpointer(self):
        """Initialize PostgreSQL checkpointer for conversation persistence."""
        try:
            # Use the PostgreSQL checkpointer from pg_checkpoint module
            if postgres_checkpointer is not None:
                logger.info("PostgreSQL checkpointer initialized successfully")
                return postgres_checkpointer
            else:
                logger.warning("PostgreSQL checkpointer not available, falling back to MemorySaver")
                # Fallback to MemorySaver if PostgreSQL is not available
                from langgraph.checkpoint.memory import MemorySaver
                return MemorySaver()
            
        except Exception as e:
            logger.error(f"Failed to initialize checkpointer: {e}")
            # Fallback to MemorySaver in case of error
            from langgraph.checkpoint.memory import MemorySaver
            logger.warning("Falling back to MemorySaver due to PostgreSQL checkpointer error")
            return MemorySaver()
    
    def _create_agent(self) -> Any:
        """Create the ReAct agent."""
        
        # Create the agent with basic parameters
        agent = create_react_agent(
            model=self.model,
            tools=self.tools,
            checkpointer=self.checkpointer,
        )
        
        logger.info("ReAct agent created successfully")
        return agent
    
    def _apply_pre_hooks(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply pre-hooks to the input state.
        
        Args:
            state: Input state before agent processing
            
        Returns:
            State after pre-hook processing
        """
        try:
            if not self.enable_pre_hooks:
                logger.info("Pre-hooks disabled, skipping")
                return state
            
            logger.info("Applying pre-hooks (content filtering and history summarization)")
            
            # Apply pre-hooks in sequence
            state = curse_word_guardrail_hook(state)
            
            # If content was flagged, return immediately
            if state.get('moderation_flagged'):
                logger.warning("Content flagged by moderation, skipping further processing.")
                return state
                
            state = history_summarizer_hook(state)
            
            logger.info("Pre-hooks applied successfully")
            return state
            
        except Exception as e:
            logger.error(f"Pre-hook processing failed: {e}")
            # Return original state if pre-hooks fail
            return {
                **state,
                'pre_hook_error': str(e)
            }
    
    def chat(self, message: str, thread_id: str = None, user_id: str = None, language: str = "en", from_number: str = None) -> Dict[str, Any]:
        """
        Main chat method for interacting with the agent with integrated guardrails.
        
        Args:
            message: User message
            thread_id: Thread ID for conversation continuity
            user_id: Optional user ID
            language: Language preference
            from_number: The user's phone number, to be passed in metadata
            
        Returns:
            Dictionary containing agent response and metadata
        """
        try:
            # Generate thread_id if not provided
            if not thread_id:
                thread_id = str(uuid.uuid4())
            
            # Create configuration for the agent
            config = RunnableConfig(
                configurable={"thread_id": thread_id},
                metadata={
                    "user_id": user_id,
                    "language": language,
                    "from_number": from_number,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Check if this is the first message in the conversation
            is_new_conversation = not self.checkpointer.get(config)

            # Prepare initial input state
            messages = []
            if is_new_conversation:
                # For new conversations, inject the system prompt first
                messages.append(SystemMessage(content=self.system_prompt))
                logger.info(f"New conversation started for thread_id: {thread_id}. Injecting system prompt.")

            messages.append(HumanMessage(content=message))
            
            initial_state = {
                "messages": messages,
                "conversation_id": thread_id,
                "user_id": user_id,
                "language": language,
                "conversation_start_time": datetime.now(),
            }
            
            logger.info(f"Processing message for thread_id: {thread_id}")
            
            # 1. Apply pre-hooks (content filtering, history summarization)
            initial_state = self._apply_pre_hooks({'messages': initial_state["messages"]})
            
            # If pre-hooks generated a response (e.g., moderation block), return it
            if 'moderation_flagged' in initial_state and len(initial_state['messages']) > 0:
                final_response_message = initial_state['messages'][-1]
                return {
                    'response': final_response_message.content,
                    'thread_id': thread_id,
                    'metadata': {
                        'moderation_flagged': True,
                        'moderation_categories': initial_state.get('moderation_categories', {})
                    }
                }

            # 2. Invoke the agent with the processed state
            final_state = self.agent.invoke(
                initial_state,
                config=config
            )

            # Handle cases where the agent invocation might fail and return None
            if final_state is None:
                logger.error(f"Agent invocation returned None for thread_id: {thread_id}. This might indicate an internal error in the graph.")
                final_state = {'messages': [AIMessage(content="I'm sorry, I encountered an issue and cannot respond at the moment.")]}
            
            # Extract the final response message
            final_response_message = final_state['messages'][-1] if final_state.get('messages') else AIMessage(content="I'm sorry, I encountered an issue and cannot respond at the moment.")
            
            # Log successful chat interaction
            logger.info(f"Chat interaction completed for thread_id: {thread_id}")

            return {
                'response': final_response_message.content,
                'thread_id': thread_id,
                'history': self.get_conversation_history(thread_id)
            }
            
        except Exception as e:
            logger.error(f"Error processing chat message: {e}")
            # Attempt to save a system error message to the conversation history
            try:
                error_message = SystemMessage(content=f"Agent Error: {e}")
                # The checkpoint is the state of the conversation, which is a dictionary.
                # The `put` method for PostgresSaver expects `config`, `checkpoint`, and `metadata`.
                checkpoint_data = {"messages": [error_message]}
                self.checkpointer.put(config, checkpoint_data, config['metadata'])
            except Exception as checkpoint_e:
                logger.error(f"Failed to save error message to checkpoint: {checkpoint_e}")
            
            return {
                'response': "I'm sorry, I encountered a system error. Please try again later.",
                'thread_id': thread_id,
                'error': str(e)
            }
    
    def get_conversation_history(self, thread_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve conversation history for a given thread.
        
        Args:
            thread_id: Thread ID to retrieve history for
            
        Returns:
            List of message dictionaries
        """
        try:
            # Get the checkpoint from memory
            config = RunnableConfig(configurable={"thread_id": thread_id})
            checkpoint_dict = self.checkpointer.get(config)
            
            if not checkpoint_dict:
                logger.warning(f"No checkpoint found for thread_id: {thread_id}")
                return []

            # Extract messages from the checkpoint dictionary
            messages = checkpoint_dict.get("channel_values", {}).get("messages", [])
            
            # Convert to dictionary format
            history = []
            for msg in messages:
                history.append({
                    "type": msg.type,
                    "content": msg.content,
                    "timestamp": getattr(msg, 'timestamp', None),
                    "id": getattr(msg, 'id', None),
                })
            
            logger.info(f"Retrieved {len(history)} messages for thread_id: {thread_id}")
            return history
            
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return []
    
    def clear_conversation(self, thread_id: str) -> bool:
        """
        Clear conversation history for a given thread.
        
        Args:
            thread_id: Thread ID to clear
            
        Returns:
            True if successful, False otherwise
        """
        if not thread_id:
            logger.warning("No thread_id provided for clearing conversation")
            return False
            
        config = {"configurable": {"thread_id": thread_id}}
        
        try:
            # To "clear" a conversation with MemorySaver, we can just save an empty state
            empty_state = {"messages": []}
            self.checkpointer.put(config, empty_state)
            
            logger.info(f"Conversation cleared for thread_id: {thread_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear conversation for thread_id {thread_id}: {e}")
            return False

    def configure_hooks(self, enable_pre_hooks: bool = True):
        """
        Enable or disable hooks at runtime.
        
        Args:
            enable_pre_hooks: Set to False to disable all pre-hooks
        """
        self.enable_pre_hooks = enable_pre_hooks
        logger.info(f"Pre-hooks enabled: {self.enable_pre_hooks}")

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the agent and its components.
        """
        health_status = {
            'agent_status': 'ok',
            'model_status': 'ok',
            'tools_status': 'ok',
            'checkpointer_status': 'ok',
            'last_checked': datetime.now().isoformat()
        }
        
        try:
            # Check model
            self.model.invoke("hello")
        except Exception as e:
            health_status['model_status'] = f"error: {e}"
            health_status['agent_status'] = 'degraded'
            logger.error(f"Health check failed at model: {e}")

        try:
            # Check tools (simple check if they exist)
            if not self.tools or len(self.tools) == 0:
                raise ValueError("No tools initialized")
        except Exception as e:
            health_status['tools_status'] = f"error: {e}"
            health_status['agent_status'] = 'degraded'
            logger.error(f"Health check failed at tools: {e}")

        try:
            # Check checkpointer (simple check if it exists)
            if not self.checkpointer:
                raise ValueError("Checkpointer not initialized")
        except Exception as e:
            health_status['checkpointer_status'] = f"error: {e}"
            health_status['agent_status'] = 'degraded'
            logger.error(f"Health check failed at checkpointer: {e}")
            
        return health_status

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the agent's performance.
        (This is a placeholder for a more robust implementation with a proper metrics store)
        """
        # In a real-world scenario, you would fetch these from a database or monitoring service
        return {
            "total_conversations": 0, # Placeholder
            "successful_chats": 0,    # Placeholder
            "failed_chats": 0,        # Placeholder
            "average_response_time": 0.0, # Placeholder
            "last_updated": datetime.now().isoformat()
        }
        
class AgentRegistry:
    """A registry to create, manage, and retrieve agent instances."""
    _agents: Dict[str, ECLAAgent] = {}

    @classmethod
    def _initialize_agents(cls):
        """Load configurations and initialize all agents."""
        if not cls._agents:
            logger.info("Initializing AgentRegistry...")
            for agent_id, config in AGENT_CONFIGURATIONS.items():
                logger.info(f"Creating agent: {agent_id}")
                cls._agents[agent_id] = ECLAAgent(agent_config=config)
            logger.info("AgentRegistry initialized with all configured agents.")

    @classmethod
    def get_agent(cls, agent_id: str) -> Optional[ECLAAgent]:
        """
        Get an initialized agent instance by its ID.

        Args:
            agent_id: The unique identifier for the agent.

        Returns:
            An instance of ECLAAgent or None if not found.
        """
        if not cls._agents:
            cls._initialize_agents()
        
        agent = cls._agents.get(agent_id)
        if not agent:
            logger.error(f"Agent with ID '{agent_id}' not found in registry.")
        return agent

# Singleton instance of the agent registry, initialized on first use.
_agent_registry = AgentRegistry()


# Wrapper functions for easy integration with web frameworks
def chat_with_agent(message: str, thread_id: str = None, agent_id: str = "ecla_sales_agent", **kwargs) -> Dict[str, Any]:
    """Wrapper function to chat with a specific agent."""
    agent = _agent_registry.get_agent(agent_id)
    if not agent:
        return {
            "response": f"I'm sorry, the requested agent '{agent_id}' is not available.",
            "thread_id": thread_id,
            "error": "Agent not found",
        }
    return agent.chat(message, thread_id, **kwargs)

def get_conversation_history(thread_id: str, agent_id: str = "ecla_sales_agent") -> List[Dict[str, Any]]:
    """Wrapper function to get conversation history for a specific agent."""
    agent = _agent_registry.get_agent(agent_id)
    if not agent:
        return [{"error": f"Agent with ID '{agent_id}' not found."}]
    return agent.get_conversation_history(thread_id)

def agent_health_check(agent_id: str = "ecla_sales_agent") -> Dict[str, Any]:
    """Wrapper function for a specific agent's health check."""
    agent = _agent_registry.get_agent(agent_id)
    if not agent:
        return {"error": f"Agent with ID '{agent_id}' not found."}
    return agent.health_check() 