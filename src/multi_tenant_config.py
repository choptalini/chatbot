"""
Multi-Tenant Configuration for SwiftReplies.ai
Manages settings for the multi-tenant WhatsApp bot system
"""

import os
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MultiTenantConfig:
    """Configuration manager for multi-tenant operations."""
    
    # Database settings
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # SwiftReplies admin user settings (default for all operations)
    # ADMIN_USER_ID = 2  # SwiftReplies admin (previous default)
    # DEFAULT_CHATBOT_ID = 2  # SwiftReplies main bot (previous default)
    # Default routing target (used by destination-based routing via WHATSAPP_SENDER)
    ADMIN_USER_ID = 2  # SwiftReplies admin (default)
    DEFAULT_CHATBOT_ID = 2  # SwiftReplies main bot
    
    # Routing strategy (local-config preferred over DB for destination-based routing)
    ROUTE_BY_DESTINATION = os.getenv("ROUTE_BY_DESTINATION", "true").lower() == "true"
    
    # Feature flags for gradual migration
    ENABLE_MULTI_TENANT = os.getenv("ENABLE_MULTI_TENANT", "true").lower() == "true"
    ENABLE_USAGE_TRACKING = os.getenv("ENABLE_USAGE_TRACKING", "true").lower() == "true"
    ENABLE_ACTIONS_CENTER = os.getenv("ENABLE_ACTIONS_CENTER", "true").lower() == "true"
    
    # WhatsApp bot settings
    DEBOUNCE_SECONDS = int(os.getenv("DEBOUNCE_SECONDS", "3"))
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "5"))
    BUSY_THRESHOLD = int(os.getenv("BUSY_THRESHOLD", "3"))
    
    # Usage limits (default values)
    DEFAULT_DAILY_MESSAGE_LIMIT = int(os.getenv("DEFAULT_DAILY_MESSAGE_LIMIT", "999999999"))
    DEFAULT_MONTHLY_MESSAGE_LIMIT = int(os.getenv("DEFAULT_MONTHLY_MESSAGE_LIMIT", "999999999"))
    DEFAULT_DAILY_CAMPAIGN_LIMIT = int(os.getenv("DEFAULT_DAILY_CAMPAIGN_LIMIT", "999999999"))
    DEFAULT_MONTHLY_CAMPAIGN_LIMIT = int(os.getenv("DEFAULT_MONTHLY_CAMPAIGN_LIMIT", "999999999"))
    
    # Phone number to user mapping (for development/testing)
    # In production, this would be managed through the database
    PHONE_TO_USER_MAPPING = {
        # Add your phone numbers here during migration period
        # Previous SwiftReplies examples (disabled):
        # "+1234567890": {"user_id": 2, "chatbot_id": 2},
        # "+9876543210": {"user_id": 2, "chatbot_id": 2},

        # Current active mapping → route this from_number to AstroSouks (user_id=6, chatbot_id=3)
        "96170895652": {"user_id": 6, "chatbot_id": 3},
        "+96170895652": {"user_id": 6, "chatbot_id": 3},
    }
    
    @classmethod
    def get_user_mapping(cls, phone_number: str) -> Dict[str, int]:
        """
        Get user and chatbot mapping for a phone number.
        Now defaults to SwiftReplies admin (User ID 2).
        """
        if not cls.ENABLE_MULTI_TENANT:
            # During migration period, use SwiftReplies admin for all
            return {
                "user_id": cls.ADMIN_USER_ID,
                "chatbot_id": cls.DEFAULT_CHATBOT_ID
            }
        
        # Check explicit mapping first
        if phone_number in cls.PHONE_TO_USER_MAPPING:
            return cls.PHONE_TO_USER_MAPPING[phone_number]
        
        # Default to SwiftReplies admin (safe fallback)
        return {
            "user_id": cls.ADMIN_USER_ID,
            "chatbot_id": cls.DEFAULT_CHATBOT_ID
        }
    
    @staticmethod
    def _normalize_number(num: Optional[str]) -> Optional[str]:
        """Normalize phone numbers to a comparable canonical form (digits only, no leading '+')."""
        if not num:
            return None
        # Remove common formatting characters and leading '+'
        cleaned = (
            str(num)
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
            .lstrip("+")
        )
        return cleaned
    
    # WhatsApp Sender to Tenant Mapping
    SENDER_TO_TENANT_MAPPING = {
        # SwiftReplies Main Bot (Default)
        "96179374241": {
            "user_id": 2,  # SwiftReplies admin
            "chatbot_id": 2,  # SwiftReplies main bot
            "agent_id": "ecla_sales_agent"
        },
        # AstroSouks Bot
        "9613451652": {
            "user_id": 6,  # AstroSouks user
            "chatbot_id": 3,  # AstroSouks chatbot
            "agent_id": "astrosouks_sales_agent"
        }
    }
    
    @classmethod
    def get_routing_for_destination(cls, to_number: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Resolve routing by destination (business) number using multi-tenant configuration.
        
        This method now supports multiple WhatsApp business numbers:
        - 96179374241: SwiftReplies (ECLA) - user_id=2, chatbot_id=2, agent=ecla_sales_agent
        - 9613451652: AstroSouks - user_id=6, chatbot_id=3, agent=astrosouks_sales_agent
        
        Args:
            to_number: The destination WhatsApp number (where the message was sent)
            
        Returns:
            Dict with user_id, chatbot_id, and agent_id if found, None otherwise
        """
        if not cls.ROUTE_BY_DESTINATION or not to_number:
            return None
            
        normalized_to = cls._normalize_number(to_number)
        if not normalized_to:
            return None
            
        # Check our sender mapping
        for sender_number, config in cls.SENDER_TO_TENANT_MAPPING.items():
            if cls._normalize_number(sender_number) == normalized_to:
                return config.copy()  # Return a copy to avoid mutations
                
        # Fallback: Check environment variables for backwards compatibility
        env_sender = os.getenv("WHATSAPP_SENDER")
        astrosouks_sender = os.getenv("ASTROSOUKS_WHATSAPP_SENDER")
        
        if env_sender and cls._normalize_number(to_number) == cls._normalize_number(env_sender):
            return {
                "user_id": cls.ADMIN_USER_ID,
                "chatbot_id": cls.DEFAULT_CHATBOT_ID,
                "agent_id": "ecla_sales_agent"
            }
        elif astrosouks_sender and cls._normalize_number(to_number) == cls._normalize_number(astrosouks_sender):
            return {
                "user_id": 6,
                "chatbot_id": 3,
                "agent_id": "astrosouks_sales_agent"
            }
            
        return None

    @classmethod
    def _match_mapping_by(cls, *, user_id: Optional[int] = None, chatbot_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Internal: find a sender mapping entry by user_id or chatbot_id.
        Returns a dict including sender_number and mapping fields if found.
        """
        for sender_number, cfg in cls.SENDER_TO_TENANT_MAPPING.items():
            if user_id is not None and cfg.get("user_id") == user_id:
                out = cfg.copy()
                out["sender_number"] = sender_number
                # Provide a friendly client key label for selection in app.state.whatsapp_clients
                out["client_key"] = "astrosouks" if int(cfg.get("chatbot_id", -1)) == 3 else "ecla"
                return out
            if chatbot_id is not None and cfg.get("chatbot_id") == chatbot_id:
                out = cfg.copy()
                out["sender_number"] = sender_number
                out["client_key"] = "astrosouks" if int(cfg.get("chatbot_id", -1)) == 3 else "ecla"
                return out
        return None

    @classmethod
    def resolve_sender_config_by_chatbot(cls, chatbot_id: Optional[int]) -> Optional[Dict[str, Any]]:
        """Resolve sender configuration (including client_key) by chatbot_id."""
        if chatbot_id is None:
            return None
        try:
            chatbot_id_int = int(chatbot_id)
        except Exception:
            return None
        return cls._match_mapping_by(chatbot_id=chatbot_id_int)

    @classmethod
    def resolve_sender_config_by_user(cls, user_id: Optional[int]) -> Optional[Dict[str, Any]]:
        """Resolve sender configuration (including client_key) by user_id."""
        if user_id is None:
            return None
        try:
            user_id_int = int(user_id)
        except Exception:
            return None
        return cls._match_mapping_by(user_id=user_id_int)
    
    @classmethod
    def get_all_sender_configs(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get all configured WhatsApp sender configurations.
        
        Returns:
            Dict mapping normalized phone numbers to their configurations
        """
        return cls.SENDER_TO_TENANT_MAPPING.copy()
    
    @classmethod
    def get_sender_config(cls, sender_number: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific sender number.
        
        Args:
            sender_number: The WhatsApp sender number to look up
            
        Returns:
            Configuration dict if found, None otherwise
        """
        normalized = cls._normalize_number(sender_number)
        for config_number, config in cls.SENDER_TO_TENANT_MAPPING.items():
            if cls._normalize_number(config_number) == normalized:
                return config.copy()
        return None
    
    @classmethod
    def should_track_usage(cls) -> bool:
        """Check if usage tracking is enabled."""
        return cls.ENABLE_USAGE_TRACKING
    
    @classmethod
    def should_use_actions_center(cls) -> bool:
        """Check if actions center is enabled."""
        return cls.ENABLE_ACTIONS_CENTER
    
    @classmethod
    def get_default_limits(cls) -> Dict[str, int]:
        """Get default usage limits."""
        return {
            "daily_message_limit": cls.DEFAULT_DAILY_MESSAGE_LIMIT,
            "monthly_message_limit": cls.DEFAULT_MONTHLY_MESSAGE_LIMIT,
            "daily_campaign_limit": cls.DEFAULT_DAILY_CAMPAIGN_LIMIT,
            "monthly_campaign_limit": cls.DEFAULT_MONTHLY_CAMPAIGN_LIMIT
        }
    
    @classmethod
    def validate_config(cls) -> Dict[str, Any]:
        """Validate configuration and return status."""
        issues = []
        
        if not cls.DATABASE_URL:
            issues.append("DATABASE_URL not set")
        
        if cls.ADMIN_USER_ID is None:
            issues.append("ADMIN_USER_ID not configured")
        
        if cls.DEFAULT_CHATBOT_ID is None:
            issues.append("DEFAULT_CHATBOT_ID not configured")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "multi_tenant_enabled": cls.ENABLE_MULTI_TENANT,
            "usage_tracking_enabled": cls.ENABLE_USAGE_TRACKING,
            "actions_center_enabled": cls.ENABLE_ACTIONS_CENTER,
            "default_user": f"SwiftReplies Admin (ID: {cls.ADMIN_USER_ID})",
            "default_chatbot": f"SwiftReplies Main Bot (ID: {cls.DEFAULT_CHATBOT_ID})"
        }

# Export commonly used values
config = MultiTenantConfig()

# Backward compatibility constants
ADMIN_USER_ID = config.ADMIN_USER_ID
DEFAULT_CHATBOT_ID = config.DEFAULT_CHATBOT_ID
ENABLE_MULTI_TENANT = config.ENABLE_MULTI_TENANT