"""
Constants and configuration for Infobip WhatsApp Methods SDK.

This module contains all API endpoints, default values, supported formats,
and other constants used throughout the SDK.
"""

from typing import List, Dict, Set

# API Configuration
DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RATE_LIMIT = 10  # requests per second
DEFAULT_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes

# API Endpoints
class Endpoints:
    """Infobip WhatsApp API endpoints."""
    
    # Base API path
    BASE_PATH = "/whatsapp/1"
    
    # Message endpoints
    TEXT_MESSAGE = f"{BASE_PATH}/message/text"
    IMAGE_MESSAGE = f"{BASE_PATH}/message/image"
    LOCATION_MESSAGE = f"{BASE_PATH}/message/location"
    TEMPLATE_MESSAGE = f"{BASE_PATH}/message/template"
    
    # Status endpoints
    MESSAGE_STATUS = f"{BASE_PATH}/message/status"
    
    # Media endpoints - These are typically full URLs from webhook payloads
    # No fixed endpoint as URLs are provided in webhook responses

# Supported Media Types
class MediaTypes:
    """Supported media types and formats."""
    
    # Image formats
    IMAGE_FORMATS: Set[str] = {
        "image/jpeg",
        "image/jpg", 
        "image/png",
        "image/webp",
        "image/gif"
    }
    
    # Video formats
    VIDEO_FORMATS: Set[str] = {
        "video/mp4",
        "video/mpeg",
        "video/3gpp"
    }
    
    # Audio formats  
    AUDIO_FORMATS: Set[str] = {
        "audio/mpeg",
        "audio/mp3",
        "audio/mp4",
        "audio/aac",
        "audio/ogg"
    }
    
    # Document formats
    DOCUMENT_FORMATS: Set[str] = {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
        "text/csv"
    }
    
    # All supported formats
    ALL_FORMATS = IMAGE_FORMATS | VIDEO_FORMATS | AUDIO_FORMATS | DOCUMENT_FORMATS
    
    @classmethod
    def is_supported_format(cls, content_type: str) -> bool:
        """Check if content type is supported."""
        return content_type.lower() in cls.ALL_FORMATS
    
    @classmethod
    def get_media_type(cls, content_type: str) -> str:
        """Get media type category from content type."""
        content_type = content_type.lower()
        
        if content_type in cls.IMAGE_FORMATS:
            return "image"
        elif content_type in cls.VIDEO_FORMATS:
            return "video"
        elif content_type in cls.AUDIO_FORMATS:
            return "audio"
        elif content_type in cls.DOCUMENT_FORMATS:
            return "document"
        else:
            return "unknown"

# File Size Limits (in bytes)
class FileLimits:
    """File size limits for different media types."""
    
    MAX_IMAGE_SIZE = 5 * 1024 * 1024      # 5MB
    MAX_VIDEO_SIZE = 16 * 1024 * 1024     # 16MB  
    MAX_AUDIO_SIZE = 16 * 1024 * 1024     # 16MB
    MAX_DOCUMENT_SIZE = 100 * 1024 * 1024 # 100MB
    
    @classmethod
    def get_size_limit(cls, media_type: str) -> int:
        """Get size limit for media type."""
        limits = {
            "image": cls.MAX_IMAGE_SIZE,
            "video": cls.MAX_VIDEO_SIZE,
            "audio": cls.MAX_AUDIO_SIZE,
            "document": cls.MAX_DOCUMENT_SIZE
        }
        return limits.get(media_type.lower(), cls.MAX_IMAGE_SIZE)

# Message Limits
class MessageLimits:
    """Limits for message content."""
    
    MAX_TEXT_LENGTH = 4096        # Maximum text message length
    MAX_CAPTION_LENGTH = 1024     # Maximum caption length
    MAX_LOCATION_NAME_LENGTH = 1000   # Maximum location name length
    MAX_LOCATION_ADDRESS_LENGTH = 1000 # Maximum location address length
    MAX_TEMPLATE_VARIABLES = 10   # Maximum template variables

# Auto-Response Templates
class AutoResponseTemplates:
    """Default auto-response templates."""
    
    # Keyword-based responses
    KEYWORD_RESPONSES: Dict[str, str] = {
        "hey": "Hey {name}! 👋 Thanks for reaching out. How can I assist you today?",
        "hello": "Hello {name}! 😊 Nice to hear from you. What can I help you with?",
        "hi": "Hi {name}! 👋 Great to connect with you. How may I help?",
        "test": "Test received successfully, {name}! ✅ Your message came through perfectly.",
        "help": "Hi {name}! 🆘 I'm here to help. You can ask me about our services or send any questions.",
        "thanks": "You're welcome, {name}! 😊 Feel free to reach out anytime.",
        "thank you": "My pleasure, {name}! 🙏 Happy to help anytime.",
        "good morning": "Good morning, {name}! ☀️ Hope you're having a great day. How can I help?",
        "good afternoon": "Good afternoon, {name}! 🌞 How can I assist you today?",
        "good evening": "Good evening, {name}! 🌙 How may I help you this evening?",
        "bye": "Goodbye, {name}! 👋 Feel free to reach out anytime if you need assistance.",
        "goodbye": "Take care, {name}! 😊 Don't hesitate to contact us if you need anything."
    }
    
    # Default response when no keyword matches
    DEFAULT_RESPONSE = "Thanks for your message, {name}! 📱 I received: '{message}'. Our team will get back to you soon!"
    
    # Business hours response
    AFTER_HOURS_RESPONSE = "Thank you for contacting us, {name}! 🌙 We're currently outside business hours, but we'll respond to your message as soon as possible during our next business day."
    
    # Error response
    ERROR_RESPONSE = "We apologize, {name}, but we're experiencing technical difficulties. Please try again later or contact our support team directly."

# Rate Limiting Configuration
class RateLimitConfig:
    """Rate limiting configuration."""
    
    # Default limits (requests per time period)
    DEFAULT_REQUESTS_PER_SECOND = 10
    DEFAULT_REQUESTS_PER_MINUTE = 100
    DEFAULT_REQUESTS_PER_HOUR = 1000
    
    # Burst allowance
    BURST_ALLOWANCE = 5
    
    # Backoff configuration
    INITIAL_BACKOFF_SECONDS = 1
    MAX_BACKOFF_SECONDS = 60
    BACKOFF_MULTIPLIER = 2

# Retry Configuration
class RetryConfig:
    """Retry logic configuration."""
    
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BACKOFF_FACTOR = 2
    DEFAULT_INITIAL_DELAY = 1.0
    DEFAULT_MAX_DELAY = 60.0
    
    # HTTP status codes that should trigger retries
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
    
    # HTTP status codes that should NOT trigger retries
    NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404}

# Validation Patterns
class ValidationPatterns:
    """Regular expression patterns for validation."""
    
    # Phone number patterns (international format)
    PHONE_NUMBER_PATTERN = r'^\+?[1-9]\d{1,14}$'  # E.164 format
    PHONE_NUMBER_SIMPLE_PATTERN = r'^[0-9+\-\s\(\)]{8,20}$'  # More flexible
    
    # URL patterns
    HTTP_URL_PATTERN = r'^https?://[^\s/$.?#].[^\s]*$'
    HTTPS_URL_PATTERN = r'^https://[^\s/$.?#].[^\s]*$'
    
    # Email pattern (basic)
    EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

# Environment Variable Names
class EnvVars:
    """Environment variable names."""
    
    # Required variables
    API_KEY = "INFOBIP_API_KEY"
    BASE_URL = "INFOBIP_BASE_URL"
    SENDER = "WHATSAPP_SENDER"
    
    # Optional configuration variables
    RATE_LIMIT = "WHATSAPP_RATE_LIMIT"
    TIMEOUT = "WHATSAPP_TIMEOUT"
    RETRY_ATTEMPTS = "WHATSAPP_RETRY_ATTEMPTS"
    MAX_FILE_SIZE = "WHATSAPP_MAX_FILE_SIZE"
    
    # Logging configuration
    LOG_LEVEL = "WHATSAPP_LOG_LEVEL"
    LOG_FORMAT = "WHATSAPP_LOG_FORMAT"

# Logging Configuration
class LogConfig:
    """Logging configuration constants."""
    
    DEFAULT_LOG_LEVEL = "INFO"
    DEFAULT_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    
    # Logger names
    MAIN_LOGGER = "infobip_whatsapp_methods"
    CLIENT_LOGGER = "infobip_whatsapp_methods.client"
    VALIDATOR_LOGGER = "infobip_whatsapp_methods.validators"
    UTILS_LOGGER = "infobip_whatsapp_methods.utils"

# HTTP Headers
class Headers:
    """Standard HTTP headers used by the SDK."""
    
    AUTHORIZATION = "Authorization"
    CONTENT_TYPE = "Content-Type"
    ACCEPT = "Accept"
    USER_AGENT = "User-Agent"
    
    # Content types
    JSON_CONTENT_TYPE = "application/json"
    FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"
    
    # Default headers
    DEFAULT_HEADERS = {
        CONTENT_TYPE: JSON_CONTENT_TYPE,
        ACCEPT: JSON_CONTENT_TYPE,
        USER_AGENT: "infobip-whatsapp-methods-sdk/1.0.0"
    }

# Status Codes
class StatusCodes:
    """HTTP and API status codes."""
    
    # Success codes
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    
    # Client error codes
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429
    
    # Server error codes
    INTERNAL_SERVER_ERROR = 500
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504

# Message Types
class MessageTypes:
    """WhatsApp message types."""
    
    TEXT = "text"
    IMAGE = "image" 
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    TEMPLATE = "template"
    
    # All supported types
    ALL_TYPES = {TEXT, IMAGE, VIDEO, AUDIO, DOCUMENT, LOCATION, CONTACT, TEMPLATE}

# Template Button Types
class TemplateButtonTypes:
    """Template message button types."""
    
    QUICK_REPLY = "QUICK_REPLY"
    URL = "URL"
    PHONE_NUMBER = "PHONE_NUMBER"
    
    ALL_TYPES = {QUICK_REPLY, URL, PHONE_NUMBER}

# Common Error Messages
class ErrorMessages:
    """Common error messages."""
    
    INVALID_PHONE_NUMBER = "Invalid phone number format. Use international format (e.g., +96170895652)."
    INVALID_COORDINATES = "Invalid coordinates. Latitude must be -90 to +90, longitude must be -180 to +180."
    INVALID_URL = "Invalid URL. Must be a valid HTTPS URL."
    MESSAGE_TOO_LONG = "Message exceeds maximum length of {max_length} characters."
    CAPTION_TOO_LONG = "Caption exceeds maximum length of {max_length} characters."
    FILE_TOO_LARGE = "File size ({size} bytes) exceeds maximum limit of {limit} bytes."
    UNSUPPORTED_FORMAT = "Unsupported file format: {format}. Supported formats: {supported}."
    AUTHENTICATION_FAILED = "Authentication failed. Please check your API key."
    RATE_LIMIT_EXCEEDED = "Rate limit exceeded. Please wait {retry_after} seconds before retrying."
    NETWORK_ERROR = "Network error occurred. Please check your connection and try again."
    TEMPLATE_NOT_FOUND = "Template '{template_name}' not found or not approved."
    INVALID_TEMPLATE_VARIABLES = "Expected {expected} variables, but got {provided}."

# Success Messages
class SuccessMessages:
    """Common success messages."""
    
    MESSAGE_SENT = "Message sent successfully with ID: {message_id}"
    MEDIA_DOWNLOADED = "Media downloaded successfully to: {file_path}"
    STATUS_UPDATED = "Message status updated successfully."
    AUTO_RESPONSE_SENT = "Auto-response sent successfully."

# Default Values
class Defaults:
    """Default values for various operations."""
    
    MEDIA_DOWNLOAD_DIR = "downloaded_media"
    AUTO_RESPONSE_SENDER_NAME = "User"
    TEMPLATE_LANGUAGE = "en"
    LOCATION_NAME = ""
    LOCATION_ADDRESS = ""
    IMAGE_CAPTION = "" 