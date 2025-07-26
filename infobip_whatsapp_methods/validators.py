"""
Input validation functions for Infobip WhatsApp Methods SDK.

This module provides comprehensive validation for all input parameters
including phone numbers, coordinates, URLs, message content, and media files.
"""

import re
import requests
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import urlparse
import logging

from .constants import (
    ValidationPatterns,
    MessageLimits,
    FileLimits,
    MediaTypes,
    ErrorMessages
)
from .exceptions import ValidationError

# Set up logging
logger = logging.getLogger(__name__)


def validate_phone_number(phone_number: str, strict: bool = False) -> bool:
    """
    Validate phone number format.
    
    Args:
        phone_number: Phone number to validate
        strict: Use strict E.164 format validation
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If phone number is invalid and strict validation
    """
    if not phone_number or not isinstance(phone_number, str):
        if strict:
            raise ValidationError(
                ErrorMessages.INVALID_PHONE_NUMBER,
                field="phone_number",
                value=phone_number
            )
        return False
    
    # Clean the phone number
    cleaned = phone_number.strip()
    
    # Choose pattern based on strictness
    pattern = ValidationPatterns.PHONE_NUMBER_PATTERN if strict else ValidationPatterns.PHONE_NUMBER_SIMPLE_PATTERN
    
    # Additional check for double plus signs
    if "++" in cleaned:
        is_valid = False
    else:
        # Validate format
        is_valid = bool(re.match(pattern, cleaned))
    
    if not is_valid and strict:
        raise ValidationError(
            ErrorMessages.INVALID_PHONE_NUMBER,
            field="phone_number", 
            value=phone_number
        )
    
    return is_valid


def validate_coordinates(latitude: float, longitude: float, strict: bool = False) -> bool:
    """
    Validate GPS coordinates.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        strict: Raise exception if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If coordinates are invalid and strict validation
    """
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        if strict:
            raise ValidationError(
                "Coordinates must be numeric values",
                field="coordinates",
                value=f"lat={latitude}, lon={longitude}"
            )
        return False
    
    # Check ranges
    lat_valid = -90 <= lat <= 90
    lon_valid = -180 <= lon <= 180
    
    is_valid = lat_valid and lon_valid
    
    if not is_valid and strict:
        error_details = []
        if not lat_valid:
            error_details.append(f"latitude {lat} not in range -90 to +90")
        if not lon_valid:
            error_details.append(f"longitude {lon} not in range -180 to +180")
        
        raise ValidationError(
            f"Invalid coordinates: {', '.join(error_details)}",
            field="coordinates",
            value=f"lat={latitude}, lon={longitude}"
        )
    
    return is_valid


def validate_url(url: str, require_https: bool = True, check_accessibility: bool = False, strict: bool = False) -> bool:
    """
    Validate URL format and optionally check accessibility.
    
    Args:
        url: URL to validate
        require_https: Require HTTPS protocol
        check_accessibility: Make HTTP request to check if URL is accessible
        strict: Raise exception if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If URL is invalid and strict validation
    """
    if not url or not isinstance(url, str):
        if strict:
            raise ValidationError(
                "URL cannot be empty",
                field="url",
                value=url
            )
        return False
    
    # Parse URL
    try:
        parsed = urlparse(url.strip())
    except Exception:
        if strict:
            raise ValidationError(
                "Invalid URL format",
                field="url",
                value=url
            )
        return False
    
    # Check basic format
    if not parsed.scheme or not parsed.netloc:
        if strict:
            raise ValidationError(
                "URL must include protocol and domain",
                field="url",
                value=url
            )
        return False
    
    # Check for supported protocols (HTTP/HTTPS only)
    if parsed.scheme.lower() not in ['http', 'https']:
        if strict:
            raise ValidationError(
                "URL must use HTTP or HTTPS protocol",
                field="url",
                value=url
            )
        return False
    
    # Check HTTPS requirement
    if require_https and parsed.scheme.lower() != 'https':
        if strict:
            raise ValidationError(
                "URL must use HTTPS protocol",
                field="url",
                value=url
            )
        return False
    
    # Check accessibility if requested
    if check_accessibility:
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            if response.status_code >= 400:
                if strict:
                    raise ValidationError(
                        f"URL not accessible (HTTP {response.status_code})",
                        field="url",
                        value=url
                    )
                return False
        except requests.RequestException as e:
            if strict:
                raise ValidationError(
                    f"URL accessibility check failed: {str(e)}",
                    field="url",
                    value=url
                )
            return False
    
    return True


def validate_message_text(text: str, max_length: Optional[int] = None, strict: bool = False) -> bool:
    """
    Validate message text content.
    
    Args:
        text: Message text to validate
        max_length: Maximum allowed length (defaults to MessageLimits.MAX_TEXT_LENGTH)
        strict: Raise exception if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If text is invalid and strict validation
    """
    if text is None:
        if strict:
            raise ValidationError(
                "Message text cannot be None",
                field="text",
                value=text
            )
        return False
    
    if not isinstance(text, str):
        if strict:
            raise ValidationError(
                "Message text must be a string",
                field="text",
                value=text
            )
        return False
    
    # Check length
    max_len = max_length or MessageLimits.MAX_TEXT_LENGTH
    if len(text) > max_len:
        if strict:
            raise ValidationError(
                ErrorMessages.MESSAGE_TOO_LONG.format(max_length=max_len),
                field="text",
                value=text
            )
        return False
    
    # Check for empty text
    if not text.strip():
        if strict:
            raise ValidationError(
                "Message text cannot be empty",
                field="text",
                value=text
            )
        return False
    
    return True


def validate_caption(caption: str, strict: bool = False) -> bool:
    """
    Validate image/media caption.
    
    Args:
        caption: Caption text to validate
        strict: Raise exception if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If caption is invalid and strict validation
    """
    if caption is None or caption == "":
        return True  # Empty caption is allowed
    
    if not isinstance(caption, str):
        if strict:
            raise ValidationError(
                "Caption must be a string",
                field="caption",
                value=caption
            )
        return False
    
    # Check length
    if len(caption) > MessageLimits.MAX_CAPTION_LENGTH:
        if strict:
            raise ValidationError(
                ErrorMessages.CAPTION_TOO_LONG.format(max_length=MessageLimits.MAX_CAPTION_LENGTH),
                field="caption",
                value=caption
            )
        return False
    
    return True


def validate_location_name(name: str, strict: bool = False) -> bool:
    """
    Validate location name.
    
    Args:
        name: Location name to validate
        strict: Raise exception if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If name is invalid and strict validation
    """
    if name is None or name == "":
        return True  # Empty name is allowed
    
    if not isinstance(name, str):
        if strict:
            raise ValidationError(
                "Location name must be a string",
                field="location_name",
                value=name
            )
        return False
    
    if len(name) > MessageLimits.MAX_LOCATION_NAME_LENGTH:
        if strict:
            raise ValidationError(
                f"Location name exceeds maximum length of {MessageLimits.MAX_LOCATION_NAME_LENGTH} characters",
                field="location_name",
                value=name
            )
        return False
    
    return True


def validate_location_address(address: str, strict: bool = False) -> bool:
    """
    Validate location address.
    
    Args:
        address: Location address to validate
        strict: Raise exception if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If address is invalid and strict validation
    """
    if address is None or address == "":
        return True  # Empty address is allowed
    
    if not isinstance(address, str):
        if strict:
            raise ValidationError(
                "Location address must be a string",
                field="location_address",
                value=address
            )
        return False
    
    if len(address) > MessageLimits.MAX_LOCATION_ADDRESS_LENGTH:
        if strict:
            raise ValidationError(
                f"Location address exceeds maximum length of {MessageLimits.MAX_LOCATION_ADDRESS_LENGTH} characters",
                field="location_address",
                value=address
            )
        return False
    
    return True


def validate_template_name(template_name: str, strict: bool = False) -> bool:
    """
    Validate template name.
    
    Args:
        template_name: Template name to validate
        strict: Raise exception if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If template name is invalid and strict validation
    """
    if not template_name or not isinstance(template_name, str):
        if strict:
            raise ValidationError(
                "Template name cannot be empty",
                field="template_name",
                value=template_name
            )
        return False
    
    # Basic format check (alphanumeric, underscore, hyphen)
    if not re.match(r'^[a-zA-Z0-9_-]+$', template_name.strip()):
        if strict:
            raise ValidationError(
                "Template name can only contain letters, numbers, underscores, and hyphens",
                field="template_name",
                value=template_name
            )
        return False
    
    return True


def validate_template_variables(variables: List[str], max_count: Optional[int] = None, strict: bool = False) -> bool:
    """
    Validate template variables.
    
    Args:
        variables: List of template variables
        max_count: Maximum number of variables allowed
        strict: Raise exception if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If variables are invalid and strict validation
    """
    if variables is None:
        return True  # None is allowed (no variables)
    
    if not isinstance(variables, list):
        if strict:
            raise ValidationError(
                "Template variables must be a list",
                field="template_variables",
                value=variables
            )
        return False
    
    # Check count
    max_vars = max_count or MessageLimits.MAX_TEMPLATE_VARIABLES
    if len(variables) > max_vars:
        if strict:
            raise ValidationError(
                f"Too many template variables. Maximum allowed: {max_vars}",
                field="template_variables",
                value=variables
            )
        return False
    
    # Check each variable
    for i, var in enumerate(variables):
        if not isinstance(var, str):
            if strict:
                raise ValidationError(
                    f"Template variable at index {i} must be a string",
                    field="template_variables",
                    value=variables
                )
            return False
    
    return True


def validate_file_size(file_size: int, media_type: str = "image", strict: bool = False) -> bool:
    """
    Validate file size against limits.
    
    Args:
        file_size: File size in bytes
        media_type: Type of media (image, video, audio, document)
        strict: Raise exception if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If file size is invalid and strict validation
    """
    if file_size < 0:
        if strict:
            raise ValidationError(
                "File size cannot be negative",
                field="file_size",
                value=file_size
            )
        return False
    
    # Get size limit for media type
    size_limit = FileLimits.get_size_limit(media_type)
    
    if file_size > size_limit:
        if strict:
            raise ValidationError(
                ErrorMessages.FILE_TOO_LARGE.format(size=file_size, limit=size_limit),
                field="file_size",
                value=file_size
            )
        return False
    
    return True


def validate_content_type(content_type: str, strict: bool = False) -> bool:
    """
    Validate media content type.
    
    Args:
        content_type: MIME content type
        strict: Raise exception if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If content type is invalid and strict validation
    """
    if not content_type or not isinstance(content_type, str):
        if strict:
            raise ValidationError(
                "Content type cannot be empty",
                field="content_type",
                value=content_type
            )
        return False
    
    # Check if supported
    is_supported = MediaTypes.is_supported_format(content_type)
    
    if not is_supported and strict:
        supported_formats = ", ".join(sorted(MediaTypes.ALL_FORMATS))
        raise ValidationError(
            ErrorMessages.UNSUPPORTED_FORMAT.format(
                format=content_type,
                supported=supported_formats
            ),
            field="content_type",
            value=content_type
        )
    
    return is_supported


def validate_message_id(message_id: str, strict: bool = False) -> bool:
    """
    Validate message ID format.
    
    Args:
        message_id: Message ID to validate
        strict: Raise exception if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If message ID is invalid and strict validation
    """
    if not message_id or not isinstance(message_id, str):
        if strict:
            raise ValidationError(
                "Message ID cannot be empty",
                field="message_id",
                value=message_id
            )
        return False
    
    # Basic format check (UUID-like or alphanumeric with hyphens)
    cleaned = message_id.strip()
    if not re.match(r'^[a-zA-Z0-9\-_]+$', cleaned):
        if strict:
            raise ValidationError(
                "Invalid message ID format",
                field="message_id",
                value=message_id
            )
        return False
    
    return True


def validate_language_code(language: str, strict: bool = False) -> bool:
    """
    Validate language code (ISO 639-1).
    
    Args:
        language: Language code to validate
        strict: Raise exception if invalid
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If language code is invalid and strict validation
    """
    if not language or not isinstance(language, str):
        if strict:
            raise ValidationError(
                "Language code cannot be empty",
                field="language",
                value=language
            )
        return False
    
    # Basic format check (2-letter code)
    cleaned = language.strip().lower()
    if not re.match(r'^[a-z]{2}$', cleaned):
        if strict:
            raise ValidationError(
                "Language code must be 2-letter ISO 639-1 format (e.g., 'en', 'ar')",
                field="language",
                value=language
            )
        return False
    
    return True


def validate_all_message_params(
    to_number: str,
    message_content: Optional[str] = None,
    media_url: Optional[str] = None,
    caption: Optional[str] = None,
    strict: bool = False
) -> Tuple[bool, List[str]]:
    """
    Validate all common message parameters.
    
    Args:
        to_number: Recipient phone number
        message_content: Message text content
        media_url: URL for media content
        caption: Caption for media
        strict: Raise exception on first validation failure
        
    Returns:
        Tuple of (is_valid, list_of_errors)
        
    Raises:
        ValidationError: If any parameter is invalid and strict validation
    """
    errors = []
    
    # Validate phone number
    try:
        if not validate_phone_number(to_number, strict=strict):
            errors.append("Invalid phone number format")
    except ValidationError as e:
        if strict:
            raise
        errors.append(str(e))
    
    # Validate message content if provided
    if message_content is not None:
        try:
            if not validate_message_text(message_content, strict=strict):
                errors.append("Invalid message text")
        except ValidationError as e:
            if strict:
                raise
            errors.append(str(e))
    
    # Validate media URL if provided
    if media_url is not None:
        try:
            if not validate_url(media_url, require_https=True, strict=strict):
                errors.append("Invalid media URL")
        except ValidationError as e:
            if strict:
                raise
            errors.append(str(e))
    
    # Validate caption if provided
    if caption is not None:
        try:
            if not validate_caption(caption, strict=strict):
                errors.append("Invalid caption")
        except ValidationError as e:
            if strict:
                raise
            errors.append(str(e))
    
    return len(errors) == 0, errors


def validate_location_params(
    latitude: float,
    longitude: float,
    name: Optional[str] = None,
    address: Optional[str] = None,
    strict: bool = False
) -> Tuple[bool, List[str]]:
    """
    Validate all location message parameters.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        name: Location name
        address: Location address
        strict: Raise exception on first validation failure
        
    Returns:
        Tuple of (is_valid, list_of_errors)
        
    Raises:
        ValidationError: If any parameter is invalid and strict validation
    """
    errors = []
    
    # Validate coordinates
    try:
        if not validate_coordinates(latitude, longitude, strict=strict):
            errors.append("Invalid coordinates")
    except ValidationError as e:
        if strict:
            raise
        errors.append(str(e))
    
    # Validate name if provided
    if name is not None:
        try:
            if not validate_location_name(name, strict=strict):
                errors.append("Invalid location name")
        except ValidationError as e:
            if strict:
                raise
            errors.append(str(e))
    
    # Validate address if provided
    if address is not None:
        try:
            if not validate_location_address(address, strict=strict):
                errors.append("Invalid location address")
        except ValidationError as e:
            if strict:
                raise
            errors.append(str(e))
    
    return len(errors) == 0, errors 