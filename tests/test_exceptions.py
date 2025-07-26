"""
Unit tests for infobip_whatsapp_methods.exceptions module.

Tests the custom exception hierarchy, ensuring that exceptions are created correctly
and that the `create_exception_from_response` function maps HTTP status codes
and response data to the appropriate exception types.
"""

import pytest
import sys
import os

# Add the parent directory to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from infobip_whatsapp_methods.exceptions import (
    WhatsAppError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
    NetworkError,
    APIError,
    create_exception_from_response
)


class TestExceptionHierarchy:
    """Test the custom exception classes."""
    
    def test_whatsapp_error_base_class(self):
        """Test the base WhatsAppError class."""
        err = WhatsAppError(
            message="Base error",
            status_code=500,
            error_code="E100",
            details={"key": "value"}
        )
        
        assert "Base error" in str(err)
        assert "500" in str(err)
        assert "E100" in str(err)
        assert "value" in str(err)
        
        err_dict = err.to_dict()
        assert err_dict["type"] == "WhatsAppError"
        assert err_dict["message"] == "Base error"
    
    def test_authentication_error(self):
        """Test the AuthenticationError class."""
        err = AuthenticationError()
        assert "Authentication failed" in str(err)
        
        err = AuthenticationError("Invalid API key")
        assert "Invalid API key" in str(err)
    
    def test_rate_limit_error(self):
        """Test the RateLimitError class."""
        err = RateLimitError(retry_after=60)
        assert "Rate limit exceeded" in str(err)
        assert "Retry After: 60s" in str(err)
    
    def test_validation_error(self):
        """Test the ValidationError class."""
        err = ValidationError("Invalid phone number", field="phone", value="123")
        assert "Invalid phone number" in str(err)
        assert "Field: phone" in str(err)
        assert "Value: 123" in str(err)


class TestCreateExceptionFromResponse:
    """Test the create_exception_from_response function."""
    
    def test_http_400_validation_error(self):
        """Test that HTTP 400 maps to ValidationError."""
        response_data = {
            "requestError": {
                "serviceException": {
                    "text": "Invalid phone number",
                    "validationErrors": [
                        {"field": "to", "message": "must not be blank"}
                    ]
                }
            }
        }
        
        err = create_exception_from_response(400, response_data)
        
        assert isinstance(err, ValidationError)
        assert "Invalid phone number" in err.message
    
    def test_http_401_authentication_error(self):
        """Test that HTTP 401 maps to AuthenticationError."""
        err = create_exception_from_response(401)
        assert isinstance(err, AuthenticationError)
    
    def test_http_429_rate_limit_error(self):
        """Test that HTTP 429 maps to RateLimitError."""
        response_data = {"retryAfter": 120}
        err = create_exception_from_response(429, response_data)
        
        assert isinstance(err, RateLimitError)
        assert err.retry_after == 120
    
    def test_http_500_api_error(self):
        """Test that HTTP 500 maps to APIError."""
        err = create_exception_from_response(500)
        assert isinstance(err, APIError)
    
    def test_http_503_network_error(self):
        """Test that HTTP 503 maps to NetworkError."""
        err = create_exception_from_response(503)
        assert isinstance(err, NetworkError)
    
    def test_unknown_error_maps_to_api_error(self):
        """Test that an unknown error code maps to APIError."""
        err = create_exception_from_response(418)  # I'm a teapot
        assert isinstance(err, APIError)


if __name__ == "__main__":
    pytest.main([__file__]) 