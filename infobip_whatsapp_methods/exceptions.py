"""
Custom exceptions for Infobip WhatsApp Methods SDK.

This module defines a comprehensive exception hierarchy for handling
different types of errors that can occur when using the Infobip WhatsApp API.
"""

from typing import Optional, Dict, Any, List


class WhatsAppError(Exception):
    """
    Base exception class for all WhatsApp API related errors.
    
    Attributes:
        message (str): Error message
        status_code (Optional[int]): HTTP status code if applicable
        error_code (Optional[str]): API specific error code
        details (Dict[str, Any]): Additional error details
    """
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
    
    def __str__(self):
        error_parts = [f"WhatsAppError: {self.message}"]
        
        if self.status_code:
            error_parts.append(f"Status Code: {self.status_code}")
        
        if self.error_code:
            error_parts.append(f"Error Code: {self.error_code}")
        
        if self.details:
            error_parts.append(f"Details: {self.details}")
        
        return " | ".join(error_parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "status_code": self.status_code,
            "error_code": self.error_code,
            "details": self.details
        }


class AuthenticationError(WhatsAppError):
    """
    Raised when authentication fails.
    
    This typically occurs when:
    - API key is invalid or expired
    - API key lacks required permissions
    - Authentication header is malformed
    """
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, **kwargs)


class RateLimitError(WhatsAppError):
    """
    Raised when API rate limits are exceeded.
    
    Attributes:
        retry_after (Optional[int]): Seconds to wait before retrying
        quota_exceeded (bool): Whether quota is exceeded vs rate limit
    """
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        quota_exceeded: bool = False,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
        self.quota_exceeded = quota_exceeded
    
    def __str__(self):
        base_str = super().__str__()
        if self.retry_after:
            base_str += f" | Retry After: {self.retry_after}s"
        if self.quota_exceeded:
            base_str += " | Quota Exceeded"
        return base_str


class ValidationError(WhatsAppError):
    """
    Raised when input validation fails.
    
    This occurs when:
    - Phone numbers are in invalid format
    - Coordinates are out of valid range
    - URLs are malformed or inaccessible
    - Message content violates constraints
    
    Attributes:
        field (Optional[str]): The field that failed validation
        value (Any): The invalid value
        validation_errors (List[str]): List of validation error messages
    """
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Any = None,
        validation_errors: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.field = field
        self.value = value
        self.validation_errors = validation_errors or []
    
    def __str__(self):
        base_str = super().__str__()
        if self.field:
            base_str += f" | Field: {self.field}"
        if self.value is not None:
            base_str += f" | Value: {self.value}"
        if self.validation_errors:
            base_str += f" | Validation Errors: {', '.join(self.validation_errors)}"
        return base_str


class NetworkError(WhatsAppError):
    """
    Raised when network-related errors occur.
    
    This includes:
    - Connection timeouts
    - DNS resolution failures  
    - Network unreachable errors
    - SSL/TLS errors
    """
    
    def __init__(self, message: str = "Network error occurred", **kwargs):
        super().__init__(message, **kwargs)


class APIError(WhatsAppError):
    """
    Raised when the API returns an error response.
    
    This covers general API errors that don't fit other specific categories.
    
    Attributes:
        api_response (Optional[Dict]): Raw API response
        user_errors (List[str]): User-facing error messages from API
    """
    
    def __init__(
        self,
        message: str,
        api_response: Optional[Dict[str, Any]] = None,
        user_errors: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.api_response = api_response
        self.user_errors = user_errors or []
    
    def __str__(self):
        base_str = super().__str__()
        if self.user_errors:
            base_str += f" | User Errors: {', '.join(self.user_errors)}"
        return base_str


class MediaError(WhatsAppError):
    """
    Raised when media-related operations fail.
    
    This includes:
    - Media URL not accessible
    - Unsupported media format
    - File size exceeds limits
    - Download failures
    - Disk space issues
    
    Attributes:
        media_url (Optional[str]): The media URL that caused the error
        file_size (Optional[int]): File size in bytes if known
        content_type (Optional[str]): Media content type if known
    """
    
    def __init__(
        self,
        message: str,
        media_url: Optional[str] = None,
        file_size: Optional[int] = None,
        content_type: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.media_url = media_url
        self.file_size = file_size
        self.content_type = content_type
    
    def __str__(self):
        base_str = super().__str__()
        if self.media_url:
            base_str += f" | Media URL: {self.media_url}"
        if self.file_size:
            base_str += f" | File Size: {self.file_size} bytes"
        if self.content_type:
            base_str += f" | Content Type: {self.content_type}"
        return base_str


class TemplateError(WhatsAppError):
    """
    Raised when template-related operations fail.
    
    This includes:
    - Template not found
    - Template not approved
    - Variable count mismatch
    - Invalid template data
    
    Attributes:
        template_name (Optional[str]): Name of the template
        variables_provided (Optional[int]): Number of variables provided
        variables_expected (Optional[int]): Number of variables expected
    """
    
    def __init__(
        self,
        message: str,
        template_name: Optional[str] = None,
        variables_provided: Optional[int] = None,
        variables_expected: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.template_name = template_name
        self.variables_provided = variables_provided
        self.variables_expected = variables_expected
    
    def __str__(self):
        base_str = super().__str__()
        if self.template_name:
            base_str += f" | Template: {self.template_name}"
        if self.variables_provided is not None and self.variables_expected is not None:
            base_str += f" | Variables: {self.variables_provided}/{self.variables_expected}"
        return base_str


# Exception mapping for HTTP status codes
HTTP_STATUS_TO_EXCEPTION = {
    400: ValidationError,
    401: AuthenticationError,
    403: AuthenticationError,
    404: APIError,
    429: RateLimitError,
    500: APIError,
    502: NetworkError,
    503: NetworkError,
    504: NetworkError,
}


def create_exception_from_response(
    status_code: int,
    response_data: Optional[Dict[str, Any]] = None,
    default_message: str = "API request failed"
) -> WhatsAppError:
    """
    Create appropriate exception based on HTTP status code and response data.
    
    Args:
        status_code: HTTP status code
        response_data: API response data
        default_message: Default error message
        
    Returns:
        Appropriate WhatsAppError subclass instance
    """
    # Extract error details from response
    message = default_message
    error_code = None
    user_errors = []
    
    if response_data:
        # Try to extract error message from various response formats
        if isinstance(response_data, dict):
            # Format 1: Direct error message
            if "error" in response_data:
                message = str(response_data["error"])
            
            # Format 2: Infobip API error format
            elif "requestError" in response_data:
                error_info = response_data["requestError"]
                if "serviceException" in error_info:
                    service_error = error_info["serviceException"]
                    message = service_error.get("text", message)
                    error_code = service_error.get("messageId")
                    
                    # Extract validation errors
                    if "validationErrors" in service_error:
                        user_errors = [
                            f"{err.get('field', 'unknown')}: {err.get('message', 'validation failed')}"
                            for err in service_error["validationErrors"]
                        ]
            
            # Format 3: User errors array
            elif "userErrors" in response_data:
                user_errors = [
                    error.get("message", "Unknown error")
                    for error in response_data["userErrors"]
                ]
                if user_errors:
                    message = "; ".join(user_errors)
    
    # Get appropriate exception class
    exception_class = HTTP_STATUS_TO_EXCEPTION.get(status_code, APIError)
    
    # Create exception with appropriate parameters
    if exception_class == RateLimitError:
        retry_after = None
        if response_data and isinstance(response_data, dict):
            retry_after = response_data.get("retryAfter")
        
        return exception_class(
            message=message,
            status_code=status_code,
            error_code=error_code,
            retry_after=retry_after,
            details={"user_errors": user_errors} if user_errors else None
        )
    
    elif exception_class == APIError:
        return exception_class(
            message=message,
            status_code=status_code,
            error_code=error_code,
            api_response=response_data,
            user_errors=user_errors
        )
    
    else:
        return exception_class(
            message=message,
            status_code=status_code,
            error_code=error_code,
            details={"user_errors": user_errors} if user_errors else None
        ) 