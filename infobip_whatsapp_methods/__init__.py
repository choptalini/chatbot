"""
Infobip WhatsApp Methods SDK

A comprehensive Python SDK for Infobip WhatsApp Business API that consolidates
all WhatsApp messaging functionality into a clean, professional, and reusable package.

Usage:
    from infobip_whatsapp_methods import WhatsAppClient
    
    client = WhatsAppClient(
        api_key="your_api_key",
        base_url="your_base_url", 
        sender="your_sender_number"
    )
    
    # Send messages
    client.send_text_message("96170895652", "Hello!")
    client.send_image("96170895652", "https://example.com/image.jpg", "Caption")
    client.send_location("96170895652", 33.983333, 35.633333, "Jounieh, Lebanon")
"""

__version__ = "1.0.0"
__author__ = "ECLA Development Team"
__email__ = "info@ecladerm.com"
__description__ = "Comprehensive SDK for Infobip WhatsApp Business API"

# Core imports - only import what exists for now
from .models import (
    MessageResponse,
    MediaDownloadResponse, 
    MediaMetadataResponse,
    StatusResponse,
    AutoResponseResult
)
from .exceptions import (
    WhatsAppError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
    NetworkError,
    APIError,
    MediaError
)

# Import client
from .client import WhatsAppClient

# Main exports
__all__ = [
    "WhatsAppClient",
    "MessageResponse", 
    "MediaDownloadResponse",
    "MediaMetadataResponse", 
    "StatusResponse",
    "AutoResponseResult",
    "WhatsAppError",
    "AuthenticationError",
    "RateLimitError", 
    "ValidationError",
    "NetworkError",
    "APIError",
    "MediaError"
] 