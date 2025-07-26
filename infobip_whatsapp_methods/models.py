"""
Response models for Infobip WhatsApp Methods SDK.

This module defines standardized response models for all API operations,
providing type-safe and consistent data structures.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class MessageStatus(Enum):
    """Enumeration of possible message statuses."""
    PENDING = "PENDING"
    PENDING_ENROUTE = "PENDING_ENROUTE"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class MediaType(Enum):
    """Enumeration of supported media types."""
    IMAGE = "image"
    DOCUMENT = "document"
    VIDEO = "video"
    AUDIO = "audio"


@dataclass
class MessageResponse:
    """
    Standardized response for message sending operations.
    
    Attributes:
        success: Whether the operation was successful
        message_id: Unique message identifier from Infobip
        status: Current message status
        error: Error message if operation failed
        timestamp: When the response was created
        api_cost: API cost for this operation (if available)
        metadata: Additional response data
    """
    success: bool
    message_id: Optional[str] = None
    status: str = ""
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    api_cost: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success_response(
        cls,
        message_id: str,
        status: str = "PENDING_ENROUTE",
        api_cost: Optional[int] = None,
        **metadata
    ) -> "MessageResponse":
        """Create a successful response."""
        return cls(
            success=True,
            message_id=message_id,
            status=status,
            api_cost=api_cost,
            metadata=metadata
        )
    
    @classmethod
    def error_response(
        cls,
        error: str,
        status_code: Optional[int] = None,
        **metadata
    ) -> "MessageResponse":
        """Create an error response."""
        return cls(
            success=False,
            error=error,
            metadata={"status_code": status_code, **metadata} if status_code else metadata
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "message_id": self.message_id,
            "status": self.status,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "api_cost": self.api_cost,
            "metadata": self.metadata
        }


@dataclass 
class MediaMetadataResponse:
    """
    Response for media metadata operations.
    
    Attributes:
        success: Whether the operation was successful
        content_type: MIME type of the media
        content_length: File size in bytes
        last_modified: When the file was last modified
        cache_control: Cache control headers
        etag: Entity tag for caching
        url: Original media URL
        error: Error message if operation failed
        metadata: Additional metadata
    """
    success: bool
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    last_modified: Optional[str] = None
    cache_control: Optional[str] = None
    etag: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_headers(cls, headers: Dict[str, str], url: str) -> "MediaMetadataResponse":
        """Create response from HTTP headers."""
        content_length = None
        if "content-length" in headers:
            try:
                content_length = int(headers["content-length"])
            except (ValueError, TypeError):
                pass
        
        return cls(
            success=True,
            content_type=headers.get("content-type"),
            content_length=content_length,
            last_modified=headers.get("last-modified"),
            cache_control=headers.get("cache-control"),
            etag=headers.get("etag"),
            url=url
        )
    
    @property
    def file_size_mb(self) -> Optional[float]:
        """Get file size in megabytes."""
        if self.content_length:
            return round(self.content_length / (1024 * 1024), 2)
        return None
    
    @property
    def is_image(self) -> bool:
        """Check if the media is an image."""
        return bool(self.content_type and self.content_type.startswith("image/"))
    
    @property
    def is_video(self) -> bool:
        """Check if the media is a video."""
        return bool(self.content_type and self.content_type.startswith("video/"))
    
    @property
    def is_audio(self) -> bool:
        """Check if the media is audio."""
        return bool(self.content_type and self.content_type.startswith("audio/"))


@dataclass
class MediaDownloadResponse:
    """
    Response for media download operations.
    
    Attributes:
        success: Whether the download was successful
        file_path: Path where the file was saved
        file_size: Size of downloaded file in bytes
        content_type: MIME type of the downloaded file
        filename: Generated or specified filename
        url: Original media URL
        error: Error message if download failed
        download_time: Time taken to download in seconds
        metadata: Additional download information
    """
    success: bool
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    content_type: Optional[str] = None
    filename: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    download_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def file_size_mb(self) -> Optional[float]:
        """Get file size in megabytes."""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "file_size_mb": self.file_size_mb,
            "content_type": self.content_type,
            "filename": self.filename,
            "url": self.url,
            "error": self.error,
            "download_time": self.download_time,
            "metadata": self.metadata
        }


@dataclass
class StatusResponse:
    """
    Response for message status operations.
    
    Attributes:
        success: Whether the status update was successful
        message_id: ID of the message that was updated
        status: New status of the message
        error: Error message if operation failed
        timestamp: When the status was updated
        metadata: Additional status information
    """
    success: bool
    message_id: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success_response(cls, message_id: str, status: str = "READ") -> "StatusResponse":
        """Create a successful status response."""
        return cls(
            success=True,
            message_id=message_id,
            status=status
        )


@dataclass
class AutoResponseResult:
    """
    Result of auto-response generation and sending.
    
    Attributes:
        success: Whether auto-response was successful
        response_text: Generated response message
        response_type: Type of response (keyword_match, default, etc.)
        message_sent: Whether the response was actually sent
        message_id: ID of sent response message (if sent)
        original_message: Original incoming message
        sender_name: Name of the message sender
        sender_number: Phone number of sender
        error: Error message if operation failed
        metadata: Additional response information
    """
    success: bool
    response_text: Optional[str] = None
    response_type: str = "default"
    message_sent: bool = False
    message_id: Optional[str] = None
    original_message: Optional[str] = None
    sender_name: Optional[str] = None
    sender_number: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def keyword_match(
        cls,
        response_text: str,
        keyword: str,
        original_message: str,
        sender_name: str,
        sender_number: str
    ) -> "AutoResponseResult":
        """Create result for keyword-matched response."""
        return cls(
            success=True,
            response_text=response_text,
            response_type="keyword_match",
            original_message=original_message,
            sender_name=sender_name,
            sender_number=sender_number,
            metadata={"matched_keyword": keyword}
        )
    
    @classmethod
    def default_response(
        cls,
        response_text: str,
        original_message: str,
        sender_name: str,
        sender_number: str
    ) -> "AutoResponseResult":
        """Create result for default response."""
        return cls(
            success=True,
            response_text=response_text,
            response_type="default",
            original_message=original_message,
            sender_name=sender_name,
            sender_number=sender_number
        )


@dataclass
class WebhookMessage:
    """
    Parsed message from webhook payload.
    
    Attributes:
        message_id: Unique message identifier
        from_number: Sender's phone number
        to_number: Recipient's phone number
        message_type: Type of message (text, image, etc.)
        text: Message text content (for text messages)
        media_url: URL of media content (for media messages)
        contact_name: Name of the sender (if available)
        received_at: When the message was received
        raw_payload: Original webhook payload
    """
    message_id: str
    from_number: str
    to_number: str
    message_type: str
    text: Optional[str] = None
    media_url: Optional[str] = None
    contact_name: Optional[str] = None
    received_at: datetime = field(default_factory=datetime.now)
    raw_payload: Optional[Dict[str, Any]] = None
    
    @property
    def is_text_message(self) -> bool:
        """Check if this is a text message."""
        return self.message_type.lower() == "text"
    
    @property
    def is_media_message(self) -> bool:
        """Check if this is a media message."""
        return self.message_type.lower() in ["image", "document", "video", "audio"]
    
    @property
    def has_media(self) -> bool:
        """Check if message has media content."""
        return bool(self.media_url)


@dataclass
class LocationData:
    """
    Structured location data for location messages.
    
    Attributes:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        name: Location name/title
        address: Full address
        country: Country name
        region: Region/state name
    """
    latitude: float
    longitude: float
    name: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    
    def validate(self) -> bool:
        """Validate coordinate ranges."""
        return (
            -90 <= self.latitude <= 90 and
            -180 <= self.longitude <= 180
        )
    
    @property
    def google_maps_url(self) -> str:
        """Generate Google Maps URL for this location."""
        return f"https://www.google.com/maps?q={self.latitude},{self.longitude}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API payload."""
        data = {
            "latitude": self.latitude,
            "longitude": self.longitude
        }
        
        if self.name:
            data["name"] = self.name
        if self.address:
            data["address"] = self.address
            
        return data


@dataclass
class TemplateData:
    """
    Template message data structure.
    
    Attributes:
        template_name: Name of the template
        language: Template language code
        header_image_url: URL for an image in the header
        body_variables: List of variables for substitution in the body
        buttons: List of button configurations
        header_variables: Variables for header section (if not an image)
    """
    template_name: str
    language: str = "en"
    header_image_url: Optional[str] = None
    body_variables: List[str] = field(default_factory=list)
    buttons: List[Dict[str, Any]] = field(default_factory=list)
    header_variables: List[str] = field(default_factory=list)

    def to_api_payload(self, from_number: str, to_number: str) -> Dict[str, Any]:
        """Convert to Infobip API payload format."""
        payload = {
            "messages": [{
                "from": from_number,
                "to": to_number,
                "content": {
                    "templateName": self.template_name,
                    "templateData": {},
                    "language": self.language
                }
            }]
        }
        
        template_data = payload["messages"][0]["content"]["templateData"]
        
        # The 'body' field with 'placeholders' is mandatory, even if empty.
        template_data["body"] = {
            "placeholders": self.body_variables
        }
        
        # Add header
        if self.header_image_url:
            template_data["header"] = {
                "type": "IMAGE",
                "mediaUrl": self.header_image_url
            }
        elif self.header_variables:
            template_data["header"] = {
                "placeholders": self.header_variables
            }
        
        # Add buttons
        if self.buttons:
            template_data["buttons"] = self.buttons
        
        return payload


# Lebanon preset locations (for convenience)
LEBANON_LOCATIONS = {
    "beirut": LocationData(
        latitude=33.888630,
        longitude=35.495480,
        name="Beirut, Lebanon",
        address="Beirut, Lebanon",
        country="Lebanon",
        region="Beirut Governorate"
    ),
    "jounieh": LocationData(
        latitude=33.983333,
        longitude=35.633333,
        name="Jounieh, Lebanon", 
        address="Jounieh, Mount Lebanon Governorate, Lebanon",
        country="Lebanon",
        region="Mount Lebanon"
    ),
    "tripoli": LocationData(
        latitude=34.436667,
        longitude=35.833333,
        name="Tripoli, Lebanon",
        address="Tripoli, North Governorate, Lebanon",
        country="Lebanon",
        region="North Governorate"
    ),
    "baalbek": LocationData(
        latitude=34.006667,
        longitude=36.204167,
        name="Baalbek, Lebanon",
        address="Baalbek, Baalbek-Hermel Governorate, Lebanon",
        country="Lebanon",
        region="Baalbek-Hermel"
    ),
    "tyre": LocationData(
        latitude=33.271992,
        longitude=35.203487,
        name="Tyre, Lebanon",
        address="Tyre, South Governorate, Lebanon",
        country="Lebanon",
        region="South Governorate"
    ),
    "sidon": LocationData(
        latitude=33.557144,
        longitude=35.369115,
        name="Sidon, Lebanon",
        address="Sidon, South Governorate, Lebanon",
        country="Lebanon",
        region="South Governorate"
    ),
    "zahle": LocationData(
        latitude=33.846667,
        longitude=35.901111,
        name="Zahle, Lebanon",
        address="Zahle, Beqaa Governorate, Lebanon",
        country="Lebanon",
        region="Beqaa Governorate"
    )
} 