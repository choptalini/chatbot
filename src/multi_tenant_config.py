"""
Multi-Tenant Configuration for SwiftReplies.ai
Manages settings for the multi-tenant WhatsApp bot system
"""

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MultiTenantConfig:
    """Configuration manager for multi-tenant operations."""
    
    # Database settings
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # SwiftReplies admin user settings (default for all operations)
    ADMIN_USER_ID = 2  # SwiftReplies admin
    DEFAULT_CHATBOT_ID = 2  # SwiftReplies main bot
    
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
        # "+1234567890": {"user_id": 2, "chatbot_id": 2},
        # "+9876543210": {"user_id": 2, "chatbot_id": 2},
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