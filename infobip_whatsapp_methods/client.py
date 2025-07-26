"""
Main WhatsApp client for Infobip WhatsApp Methods SDK.

This module contains the core WhatsAppClient class that provides a unified interface
for all WhatsApp messaging operations using the Infobip WhatsApp Business API.
"""

import os
import requests
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from urllib.parse import urlparse
import mimetypes

from .constants import (
    Endpoints,
    Headers,
    StatusCodes,
    AutoResponseTemplates,
    MediaTypes,
    FileLimits,
    Defaults,
    DEFAULT_TIMEOUT,
    DEFAULT_RETRY_ATTEMPTS
)
from .models import (
    MessageResponse,
    MediaMetadataResponse,
    MediaDownloadResponse,
    StatusResponse,
    AutoResponseResult,
    LocationData,
    TemplateData,
    LEBANON_LOCATIONS
)
from .exceptions import (
    WhatsAppError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
    NetworkError,
    APIError,
    MediaError,
    TemplateError,
    create_exception_from_response
)
from .validators import (
    validate_phone_number,
    validate_coordinates,
    validate_url,
    validate_message_text,
    validate_caption,
    validate_template_name,
    validate_template_variables,
    validate_file_size,
    validate_content_type,
    validate_message_id,
    validate_all_message_params,
    validate_location_params
)
from .models import WebhookMessage

# Set up logging
logger = logging.getLogger(__name__)


class WhatsAppClient:
    """
    Comprehensive WhatsApp client for Infobip API.
    
    This client provides a unified interface for all WhatsApp messaging operations
    including text messages, images, locations, templates, media handling, and
    auto-response functionality.
    
    Example:
        client = WhatsAppClient(
            api_key="your_api_key",
            base_url="your_base_url",
            sender="96179374241"
        )
        
        # Send a text message
        response = client.send_text_message("96170895652", "Hello!")
        
        # Send an image with caption
        response = client.send_image(
            "96170895652", 
            "https://example.com/image.jpg",
            "Check this out!"
        )
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        sender: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        enable_validation: bool = True,
        enable_logging: bool = True
    ):
        """
        Initialize WhatsApp client.
        
        Args:
            api_key: Infobip API key (or set INFOBIP_API_KEY env var)
            base_url: Infobip base URL (or set INFOBIP_BASE_URL env var)
            sender: WhatsApp sender number (or set WHATSAPP_SENDER env var)
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts for failed requests
            enable_validation: Enable input validation
            enable_logging: Enable request/response logging
            
        Raises:
            AuthenticationError: If required credentials are missing
        """
        # Load configuration from environment or parameters
        self.api_key = api_key or os.getenv("INFOBIP_API_KEY")
        self.base_url = base_url or os.getenv("INFOBIP_BASE_URL")
        self.sender = sender or os.getenv("WHATSAPP_SENDER")
        
        # Validate required parameters
        if not all([self.api_key, self.base_url, self.sender]):
            missing = []
            if not self.api_key:
                missing.append("api_key (or INFOBIP_API_KEY)")
            if not self.base_url:
                missing.append("base_url (or INFOBIP_BASE_URL)")
            if not self.sender:
                missing.append("sender (or WHATSAPP_SENDER)")
            
            raise AuthenticationError(
                f"Missing required parameters: {', '.join(missing)}"
            )
        
        # Normalize base URL
        self.base_url = self._normalize_base_url(self.base_url)
        
        # Configuration
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.enable_validation = enable_validation
        self.enable_logging = enable_logging
        
        # Setup HTTP headers
        self.headers = {
            Headers.AUTHORIZATION: f"App {self.api_key}",
            **Headers.DEFAULT_HEADERS
        }
        
        # Create media download directory
        self.media_dir = Path(Defaults.MEDIA_DOWNLOAD_DIR)
        self.media_dir.mkdir(exist_ok=True)
        
        # Log initialization
        if self.enable_logging:
            logger.info(f"WhatsApp client initialized - Sender: {self.sender}")
    
    def _normalize_base_url(self, url: str) -> str:
        """Normalize base URL to include https:// if missing."""
        if not url.startswith(('http://', 'https://')):
            return f"https://{url}"
        return url.rstrip('/')
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> requests.Response:
        """
        Make HTTP request with retry logic and error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            payload: Request payload
            **kwargs: Additional request parameters
            
        Returns:
            Response object
            
        Raises:
            WhatsAppError: On request failure
        """
        url = f"{self.base_url}{endpoint}"
        
        # Log request
        if self.enable_logging:
            logger.info(f"Making {method} request to {endpoint}")
            if payload:
                logger.debug(f"Request payload: {payload}")
        
        last_exception = None
        
        for attempt in range(self.retry_attempts + 1):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    json=payload if method.upper() in ['POST', 'PUT', 'PATCH'] else None,
                    headers=self.headers,
                    timeout=self.timeout,
                    **kwargs
                )
                
                # Log response
                if self.enable_logging:
                    logger.info(f"Response status: {response.status_code}")
                    logger.debug(f"Response headers: {dict(response.headers)}")
                
                # Handle rate limiting
                if response.status_code == StatusCodes.TOO_MANY_REQUESTS:
                    if attempt < self.retry_attempts:
                        retry_after = int(response.headers.get('Retry-After', 1))
                        logger.warning(f"Rate limited, retrying after {retry_after}s")
                        time.sleep(retry_after)
                        continue
                
                return response
                
            except requests.exceptions.Timeout as e:
                last_exception = NetworkError(f"Request timeout after {self.timeout}s")
                if attempt < self.retry_attempts:
                    logger.warning(f"Request timeout, retrying (attempt {attempt + 1})")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                    
            except requests.exceptions.ConnectionError as e:
                last_exception = NetworkError(f"Connection error: {str(e)}")
                if attempt < self.retry_attempts:
                    logger.warning(f"Connection error, retrying (attempt {attempt + 1})")
                    time.sleep(2 ** attempt)
                    continue
                    
            except requests.exceptions.RequestException as e:
                last_exception = NetworkError(f"Request error: {str(e)}")
                break
        
        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        else:
            raise NetworkError("All retry attempts failed")
    
    def _parse_send_response(self, response_data: Dict[str, Any]) -> MessageResponse:
        """Helper to parse a successful send message response."""
        # The response for a single message doesn't have the "messages" array
        if "messages" in response_data and isinstance(response_data["messages"], list) and response_data["messages"]:
            message_info = response_data["messages"][0]
        else:
            message_info = response_data

        message_id = message_info.get("messageId")
        status = message_info.get("status", {}).get("name")

        if not message_id:
            return MessageResponse.error_response(
                "Could not parse messageId from API response", 
                metadata=response_data
            )

        return MessageResponse.success_response(
            message_id=message_id, 
            status=status, 
            metadata=response_data
        )
    
    def send_text_message(
        self,
        to_number: str,
        message: str,
        validate_input: Optional[bool] = None
    ) -> MessageResponse:
        """
        Send a text message.
        
        Args:
            to_number: Recipient phone number (international format)
            message: Message text content
            validate_input: Override default validation setting
            
        Returns:
            MessageResponse with send result
            
        Raises:
            ValidationError: If input validation fails
            WhatsAppError: On API error
            
        Example:
            response = client.send_text_message(
                "96170895652", 
                "Hello! This is a test message."
            )
            print(f"Message sent with ID: {response.message_id}")
        """
        # Input validation
        if validate_input or (validate_input is None and self.enable_validation):
            validate_phone_number(to_number, strict=True)
            validate_message_text(message, strict=True)
        
        # Prepare payload
        payload = {
            "from": self.sender,
            "to": to_number,
            "content": {
                "text": message
            }
        }
        
        try:
            # Make API request
            response = self._make_request("POST", Endpoints.TEXT_MESSAGE, payload)
            
            if response.status_code in [StatusCodes.OK, StatusCodes.ACCEPTED]:
                return self._parse_send_response(response.json())
            else:
                raise create_exception_from_response(response)
            
        except ValidationError as e:
            raise
        except Exception as e:
            logger.error(f"Unexpected error sending text message: {e}")
            return MessageResponse.error_response(error=f"Unexpected error: {str(e)}")
    
    def send_image(
        self,
        to_number: str,
        image_url: str,
        caption: str = "",
        validate_input: Optional[bool] = None
    ) -> MessageResponse:
        """
        Send an image message.
        
        Args:
            to_number: Recipient phone number
            image_url: URL of the image to send
            caption: Optional image caption
            validate_input: Override default validation setting
            
        Returns:
            MessageResponse with send result
            
        Raises:
            ValidationError: If input validation fails
            WhatsAppError: On API error
            
        Example:
            response = client.send_image(
                "96170895652",
                "https://example.com/image.jpg",
                "Check out this image!"
            )
        """
        # Input validation
        if validate_input or (validate_input is None and self.enable_validation):
            validate_phone_number(to_number, strict=True)
            validate_url(image_url, require_https=True, strict=True)
            if caption:
                validate_caption(caption, strict=True)
        
        # Prepare payload
        payload = {
            "from": self.sender,
            "to": to_number,
            "content": {
                "mediaUrl": image_url
            }
        }
        
        # Add caption if provided
        if caption:
            payload["content"]["caption"] = caption
        
        try:
            # Make API request
            response = self._make_request("POST", Endpoints.IMAGE_MESSAGE, payload)

            if response.status_code in [StatusCodes.OK, StatusCodes.ACCEPTED]:
                return self._parse_send_response(response.json())
            else:
                raise create_exception_from_response(response)
            
        except ValidationError as e:
            raise
        except Exception as e:
            logger.error(f"Unexpected error sending image: {e}")
            return MessageResponse.error_response(error=f"Unexpected error: {str(e)}")
    
    def send_location(
        self,
        to_number: str,
        latitude: float,
        longitude: float,
        name: str = "",
        address: str = "",
        validate_input: Optional[bool] = None
    ) -> MessageResponse:
        """
        Send a location message.
        
        Args:
            to_number: Recipient phone number
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            name: Location name/title
            address: Location address
            validate_input: Override default validation setting
            
        Returns:
            MessageResponse with send result
            
        Raises:
            ValidationError: If input validation fails
            WhatsAppError: On API error
            
        Example:
            # Send Jounieh, Lebanon location
            response = client.send_location(
                "96170895652",
                33.983333,
                35.633333,
                "Jounieh, Lebanon",
                "Jounieh, Mount Lebanon Governorate, Lebanon"
            )
        """
        # Input validation
        if validate_input or (validate_input is None and self.enable_validation):
            is_valid, errors = validate_location_params(
                latitude, longitude, name, address, strict=True
            )
        
        # Prepare payload
        payload = {
            "from": self.sender,
            "to": to_number,
            "content": {
                "latitude": latitude,
                "longitude": longitude
            }
        }
        
        # Add optional fields
        if name:
            payload["content"]["name"] = name
        if address:
            payload["content"]["address"] = address
        
        try:
            # Make API request
            response = self._make_request("POST", Endpoints.LOCATION_MESSAGE, payload)
            
            if response.status_code in [StatusCodes.OK, StatusCodes.ACCEPTED]:
                return self._parse_send_response(response.json())
            else:
                raise create_exception_from_response(response)
            
        except ValidationError as e:
            raise
        except Exception as e:
            logger.error(f"Unexpected error sending location: {e}")
            return MessageResponse.error_response(error=f"Unexpected error: {str(e)}")
    
    def send_location_preset(
        self,
        to_number: str,
        preset_name: str,
        validate_input: Optional[bool] = None
    ) -> MessageResponse:
        """
        Send a preset location (Lebanon locations).
        
        Args:
            to_number: Recipient phone number
            preset_name: Preset location name (beirut, jounieh, tripoli, etc.)
            validate_input: Override default validation setting
            
        Returns:
            MessageResponse with send result
            
        Raises:
            ValidationError: If preset location not found
            
        Example:
            # Send Jounieh location
            response = client.send_location_preset("96170895652", "jounieh")
        """
        preset_name = preset_name.lower()
        
        if preset_name not in LEBANON_LOCATIONS:
            available = ", ".join(LEBANON_LOCATIONS.keys())
            raise ValidationError(
                f"Unknown preset location: {preset_name}. Available: {available}",
                field="preset_name",
                value=preset_name
            )
        
        location = LEBANON_LOCATIONS[preset_name]
        
        return self.send_location(
            to_number=to_number,
            latitude=location.latitude,
            longitude=location.longitude,
            name=location.name,
            address=location.address,
            validate_input=validate_input
        )
    
    def send_template(
        self,
        to_number: str,
        template_name: str,
        language: str = "en",
        header_image_url: Optional[str] = None,
        body_variables: Optional[List[str]] = None,
        buttons: Optional[List[Dict[str, Any]]] = None,
        validate_input: Optional[bool] = None
    ) -> MessageResponse:
        """
        Send a template message.
        
        Args:
            to_number: Recipient phone number
            template_name: Name of the approved template
            language: Template language code
            header_image_url: URL for the header image
            body_variables: List of variables for template body substitution
            buttons: List of button configurations
            validate_input: Override default validation setting
            
        Returns:
            MessageResponse with send result
            
        Raises:
            ValidationError: If input validation fails
            WhatsAppError: On API error
            
        Example:
            response = client.send_template(
                "96170895652",
                "swiftreplies_introduction",
                body_variables=["Antonio"],
                buttons=[{"type": "QUICK_REPLY", "parameter": "get_started"}]
            )
        """
        # Input validation
        if validate_input or (validate_input is None and self.enable_validation):
            validate_phone_number(to_number, strict=True)
            validate_template_name(template_name, strict=True)
            if body_variables:
                validate_template_variables(body_variables, strict=True)
        
        # Prepare template data
        template_data = TemplateData(
            template_name=template_name,
            language=language,
            header_image_url=header_image_url,
            body_variables=body_variables or [],
            buttons=buttons or []
        )
        
        # Convert to API payload
        payload = template_data.to_api_payload(self.sender, to_number)
        
        try:
            # Make API request
            response = self._make_request("POST", Endpoints.TEMPLATE_MESSAGE, payload)
            
            if response.status_code in [StatusCodes.OK, StatusCodes.ACCEPTED]:
                return self._parse_send_response(response.json())
            else:
                raise create_exception_from_response(response)
            
        except ValidationError as e:
            raise
        except Exception as e:
            logger.error(f"Unexpected error sending template: {e}")
            return MessageResponse.error_response(error=f"Unexpected error: {str(e)}")

    def send_christmas_offer(self, to_number: str) -> MessageResponse:
        """
        Sends the specific 'ecla_christmas_offer' template to a user.

        This is a pre-configured method for a specific marketing campaign.

        Args:
            to_number: The recipient's phone number.

        Returns:
            MessageResponse with the send result.
        """
        return self.send_template(
            to_number=to_number,
            template_name="ecla_christmas_offer",
            language="en",
            header_image_url="https://odvrvwoyqcfnwcvlbnip.supabase.co/storage/v1/object/public/swiftmessages.images//ecla_christmas_offer.jpeg",
        )

    def send_raw_template(self, payload: Dict[str, Any]) -> MessageResponse:
        """
        Sends a raw, pre-constructed template message payload.
        This is used for complex templates like carousels that are not
        fully supported by the simplified send_template method.

        Args:
            payload: The complete JSON payload for the message.

        Returns:
            MessageResponse with the send result.
        """
        try:
            # The endpoint for all template messages is the same.
            response = self._make_request("POST", Endpoints.TEMPLATE_MESSAGE, payload)

            if response.status_code in [StatusCodes.OK, StatusCodes.ACCEPTED]:
                return self._parse_send_response(response.json())
            else:
                raise create_exception_from_response(response)

        except Exception as e:
            logger.error(f"Unexpected error sending raw template: {e}")
            return MessageResponse.error_response(error=f"Unexpected error: {str(e)}")
    
    def get_media_metadata(
        self,
        media_url: str,
        validate_input: Optional[bool] = None
    ) -> MediaMetadataResponse:
        """
        Get metadata for media file.
        
        Args:
            media_url: URL of the media file
            validate_input: Override default validation setting
            
        Returns:
            MediaMetadataResponse with metadata
            
        Raises:
            ValidationError: If input validation fails
            MediaError: If metadata retrieval fails
            
        Example:
            metadata = client.get_media_metadata("https://example.com/image.jpg")
            print(f"File size: {metadata.file_size_mb} MB")
        """
        # Input validation
        if validate_input or (validate_input is None and self.enable_validation):
            validate_url(media_url, require_https=True, strict=True)
        
        try:
            # Make HEAD request to get metadata
            response = requests.head(
                media_url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            if response.status_code >= 400:
                return MediaMetadataResponse(
                    success=False,
                    error=f"Failed to get metadata: HTTP {response.status_code}",
                    url=media_url
                )
            
            return MediaMetadataResponse.from_headers(dict(response.headers), media_url)
            
        except requests.RequestException as e:
            return MediaMetadataResponse(
                success=False,
                error=f"Request failed: {str(e)}",
                url=media_url
            )
    
    def download_media(
        self,
        media_url: str,
        save_path: Optional[str] = None,
        filename: Optional[str] = None,
        validate_input: Optional[bool] = None
    ) -> MediaDownloadResponse:
        """
        Download media file from URL.
        
        Args:
            media_url: URL of the media file
            save_path: Directory to save file (default: downloaded_media/)
            filename: Custom filename (auto-generated if not provided)
            validate_input: Override default validation setting
            
        Returns:
            MediaDownloadResponse with download result
            
        Raises:
            ValidationError: If input validation fails
            MediaError: If download fails
            
        Example:
            result = client.download_media("https://example.com/image.jpg")
            print(f"Downloaded to: {result.file_path}")
        """
        # Input validation
        if validate_input or (validate_input is None and self.enable_validation):
            validate_url(media_url, require_https=True, strict=True)
        
        start_time = time.time()
        
        try:
            # Get metadata first
            metadata = self.get_media_metadata(media_url, validate_input=False)
            
            if not metadata.success:
                return MediaDownloadResponse(
                    success=False,
                    error=f"Failed to get metadata: {metadata.error}",
                    url=media_url
                )
            
            # Validate file size and type
            if metadata.content_length:
                media_type = MediaTypes.get_media_type(metadata.content_type or "")
                if not validate_file_size(metadata.content_length, media_type):
                    return MediaDownloadResponse(
                        success=False,
                        error=f"File too large: {metadata.content_length} bytes",
                        url=media_url,
                        file_size=metadata.content_length
                    )
            
            # Determine save path and filename
            if save_path:
                save_dir = Path(save_path)
            else:
                save_dir = self.media_dir
            
            save_dir.mkdir(exist_ok=True)
            
            if not filename:
                # Auto-generate filename
                parsed_url = urlparse(media_url)
                path_name = os.path.basename(parsed_url.path)
                
                if path_name and '.' in path_name:
                    filename = path_name
                else:
                    # Generate filename based on content type
                    ext = mimetypes.guess_extension(metadata.content_type or "") or ".bin"
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"media_{timestamp}{ext}"
            
            file_path = save_dir / filename
            
            # Download file
            response = requests.get(
                media_url,
                headers=self.headers,
                timeout=self.timeout,
                stream=True
            )
            
            if response.status_code >= 400:
                return MediaDownloadResponse(
                    success=False,
                    error=f"Download failed: HTTP {response.status_code}",
                    url=media_url
                )
            
            # Save file
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Get actual file size
            actual_size = file_path.stat().st_size
            download_time = time.time() - start_time
            
            return MediaDownloadResponse(
                success=True,
                file_path=str(file_path),
                file_size=actual_size,
                content_type=metadata.content_type,
                filename=filename,
                url=media_url,
                download_time=download_time
            )
            
        except Exception as e:
            return MediaDownloadResponse(
                success=False,
                error=f"Download failed: {str(e)}",
                url=media_url,
                download_time=time.time() - start_time
            )
    
    def mark_as_read(
        self,
        message_id: str,
        validate_input: Optional[bool] = None
    ) -> StatusResponse:
        """
        Mark a message as read.
        
        Args:
            message_id: ID of the message to mark as read
            validate_input: Override default validation setting
            
        Returns:
            StatusResponse with operation result
            
        Raises:
            ValidationError: If input validation fails
            WhatsAppError: On API error
            
        Example:
            response = client.mark_as_read("message_id_123")
        """
        # Input validation
        if validate_input or (validate_input is None and self.enable_validation):
            validate_message_id(message_id, strict=True)
        
        # Prepare payload
        payload = {
            "messageId": message_id,
            "status": "READ"
        }
        
        try:
            # Make API request
            response = self._make_request("POST", Endpoints.MESSAGE_STATUS, payload)
            response_data = self._handle_response(response)
            
            return StatusResponse.success_response(message_id, "READ")
            
        except WhatsAppError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error marking message as read: {e}")
            return StatusResponse(
                success=False,
                message_id=message_id,
                error=f"Unexpected error: {str(e)}"
            )
    
    def auto_respond(
        self,
        incoming_message: str,
        sender_name: str = Defaults.AUTO_RESPONSE_SENDER_NAME,
        sender_number: Optional[str] = None,
        send_response: bool = True,
        custom_templates: Optional[Dict[str, str]] = None,
        validate_input: Optional[bool] = None
    ) -> AutoResponseResult:
        """
        Generate and optionally send an auto-response.
        
        Args:
            incoming_message: The incoming message text
            sender_name: Name of the sender (for personalization)
            sender_number: Phone number to send response to
            send_response: Whether to actually send the response
            custom_templates: Custom response templates
            validate_input: Override default validation setting
            
        Returns:
            AutoResponseResult with response details
            
        Example:
            result = client.auto_respond(
                "Hey there!",
                sender_name="Antonio",
                sender_number="96170895652"
            )
            print(f"Sent response: {result.response_text}")
        """
        # Input validation
        if validate_input or (validate_input is None and self.enable_validation):
            validate_message_text(incoming_message, strict=True)
            if sender_number and send_response:
                validate_phone_number(sender_number, strict=True)
        
        # Generate response
        response_text = self._generate_auto_response(
            incoming_message, sender_name, custom_templates
        )
        
        # Determine response type
        response_type = self._get_response_type(incoming_message, custom_templates)
        
        # Create base result
        result = AutoResponseResult(
            success=True,
            response_text=response_text,
            response_type=response_type,
            original_message=incoming_message,
            sender_name=sender_name,
            sender_number=sender_number
        )
        
        # Send response if requested and phone number provided
        if send_response and sender_number:
            try:
                message_response = self.send_text_message(
                    sender_number, response_text, validate_input=False
                )
                
                if message_response.success:
                    result.message_sent = True
                    result.message_id = message_response.message_id
                else:
                    result.error = f"Failed to send response: {message_response.error}"
                    result.success = False
                    
            except Exception as e:
                result.error = f"Failed to send response: {str(e)}"
                result.success = False
        
        return result
    
    def _generate_auto_response(
        self,
        message: str,
        sender_name: str,
        custom_templates: Optional[Dict[str, str]] = None
    ) -> str:
        """Generate auto-response text based on incoming message."""
        message_lower = message.lower().strip()
        
        # Use custom templates if provided, otherwise use defaults
        templates = custom_templates or AutoResponseTemplates.KEYWORD_RESPONSES
        
        # Check for exact matches first
        if message_lower in templates:
            return templates[message_lower].format(name=sender_name, message=message)
        
        # Check for partial matches
        for keyword, template in templates.items():
            if keyword in message_lower:
                return template.format(name=sender_name, message=message)
        
        # Default response
        return AutoResponseTemplates.DEFAULT_RESPONSE.format(
            name=sender_name, message=message
        )
    
    def _get_response_type(
        self,
        message: str,
        custom_templates: Optional[Dict[str, str]] = None
    ) -> str:
        """Determine the type of auto-response generated."""
        message_lower = message.lower().strip()
        templates = custom_templates or AutoResponseTemplates.KEYWORD_RESPONSES
        
        # Check for exact match
        if message_lower in templates:
            return "keyword_match"
        
        # Check for partial match
        for keyword in templates.keys():
            if keyword in message_lower:
                return "keyword_match"
        
        return "default"
    
    def get_client_info(self) -> Dict[str, Any]:
        """
        Get client configuration information.
        
        Returns:
            Dictionary with client configuration
        """
        return {
            "sender": self.sender,
            "base_url": self.base_url,
            "timeout": self.timeout,
            "retry_attempts": self.retry_attempts,
            "validation_enabled": self.enable_validation,
            "logging_enabled": self.enable_logging,
            "media_directory": str(self.media_dir),
            "available_presets": list(LEBANON_LOCATIONS.keys())
        }
    
    def parse_webhook_payload(self, payload: Dict[str, Any]) -> List["WebhookMessage"]:
        """
        Parse incoming webhook payload into a list of WebhookMessage objects.
        
        Args:
            payload: The raw webhook payload from Infobip
            
        Returns:
            A list of parsed WebhookMessage objects
        """
        messages = []
        
        if "results" not in payload:
            logger.warning("Webhook payload missing 'results' key")
            return messages
        
        for result in payload["results"]:
            try:
                message_type = result.get("message", {}).get("type", "UNKNOWN").lower()
                
                message = WebhookMessage(
                    message_id=result.get("messageId"),
                    from_number=result.get("from"),
                    to_number=result.get("to"),
                    message_type=message_type,
                    contact_name=result.get("contact", {}).get("name"),
                    received_at=datetime.fromisoformat(result.get("receivedAt")),
                    raw_payload=result
                )
                
                if message_type == "text":
                    message.text = result.get("message", {}).get("text")
                elif message_type in ["image", "video", "audio", "document"]:
                    message.media_url = result.get("message", {}).get("url")
                
                messages.append(message)
                
            except Exception as e:
                logger.error(f"Error parsing webhook message: {e} | Payload: {result}")
        
        return messages 