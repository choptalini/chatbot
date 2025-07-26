"""
Unit tests for infobip_whatsapp_methods.validators module.

Tests all validation functions with comprehensive coverage of valid inputs,
invalid inputs, edge cases, and error handling scenarios.
"""

import pytest
from unittest.mock import patch, Mock
import sys
import os

# Add the parent directory to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from infobip_whatsapp_methods.validators import (
    validate_phone_number,
    validate_coordinates,
    validate_url,
    validate_message_text,
    validate_caption,
    validate_location_name,
    validate_location_address,
    validate_template_name,
    validate_template_variables,
    validate_file_size,
    validate_content_type,
    validate_message_id,
    validate_language_code,
    validate_all_message_params,
    validate_location_params
)
from infobip_whatsapp_methods.exceptions import ValidationError


class TestPhoneNumberValidation:
    """Test phone number validation."""
    
    def test_valid_phone_numbers(self):
        """Test valid phone number formats."""
        valid_numbers = [
            "+96170895652",
            "96170895652", 
            "+1234567890",
            "1234567890",
            "+44123456789",
            "0044123456789"
        ]
        
        for number in valid_numbers:
            assert validate_phone_number(number) == True
    
    def test_invalid_phone_numbers(self):
        """Test invalid phone number formats."""
        invalid_numbers = [
            "",
            None,
            "123",  # Too short
            "abc123def",  # Contains letters
            "++96170895652",  # Double plus
            "123-456-7890-1234567890",  # Too long
        ]
        
        for number in invalid_numbers:
            assert validate_phone_number(number) == False
    
    def test_strict_validation_raises_exception(self):
        """Test that strict validation raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_phone_number("invalid", strict=True)
        
        with pytest.raises(ValidationError):
            validate_phone_number("", strict=True)
    
    def test_strict_validation_passes_valid(self):
        """Test that strict validation passes for valid numbers."""
        assert validate_phone_number("+96170895652", strict=True) == True


class TestCoordinateValidation:
    """Test coordinate validation."""
    
    def test_valid_coordinates(self):
        """Test valid coordinate ranges."""
        valid_coords = [
            (0, 0),
            (33.983333, 35.633333),  # Jounieh, Lebanon
            (-90, -180),  # Edge cases
            (90, 180),
            (45.5, -122.68)  # Portland, OR
        ]
        
        for lat, lon in valid_coords:
            assert validate_coordinates(lat, lon) == True
    
    def test_invalid_coordinates(self):
        """Test invalid coordinate ranges."""
        invalid_coords = [
            (91, 0),    # Latitude too high
            (-91, 0),   # Latitude too low  
            (0, 181),   # Longitude too high
            (0, -181),  # Longitude too low
            (91, 181),  # Both invalid
            ("abc", 0), # Non-numeric
            (0, "def")  # Non-numeric
        ]
        
        for lat, lon in invalid_coords:
            assert validate_coordinates(lat, lon) == False
    
    def test_strict_coordinate_validation(self):
        """Test strict coordinate validation."""
        with pytest.raises(ValidationError):
            validate_coordinates(91, 0, strict=True)
        
        with pytest.raises(ValidationError):
            validate_coordinates("abc", 0, strict=True)


class TestUrlValidation:
    """Test URL validation."""
    
    def test_valid_urls(self):
        """Test valid URL formats."""
        valid_urls = [
            "https://example.com",
            "https://cdn.shopify.com/image.jpg",
            "https://api.infobip.com/whatsapp/message",
            "http://localhost:8000/webhook",
        ]
        
        for url in valid_urls:
            # Test with HTTPS not required
            assert validate_url(url, require_https=False) == True
    
    def test_invalid_urls(self):
        """Test invalid URL formats."""
        invalid_urls = [
            "",
            None,
            "not-a-url",
            "ftp://example.com",  # Wrong protocol
            "https://",  # Missing domain
            "example.com",  # Missing protocol
        ]
        
        for url in invalid_urls:
            assert validate_url(url, require_https=False) == False
    
    def test_https_requirement(self):
        """Test HTTPS requirement."""
        # HTTP URL should fail when HTTPS required
        assert validate_url("http://example.com", require_https=True) == False
        # HTTPS URL should pass
        assert validate_url("https://example.com", require_https=True) == True
    
    @patch('infobip_whatsapp_methods.validators.requests.head')
    def test_url_accessibility_check(self, mock_head):
        """Test URL accessibility checking."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response
        
        assert validate_url("https://example.com", check_accessibility=True) == True
        
        # Mock failed response
        mock_response.status_code = 404
        assert validate_url("https://example.com", check_accessibility=True) == False


class TestMessageTextValidation:
    """Test message text validation."""
    
    def test_valid_message_text(self):
        """Test valid message text."""
        valid_texts = [
            "Hello world!",
            "Test message with emoji 😊",
            "A" * 4095,  # Just under limit
            "Multi\nline\nmessage",
        ]
        
        for text in valid_texts:
            assert validate_message_text(text) == True
    
    def test_invalid_message_text(self):
        """Test invalid message text."""
        invalid_texts = [
            None,
            123,  # Not a string
            "",   # Empty string
            "   ", # Only whitespace
            "A" * 4097,  # Over limit
        ]
        
        for text in invalid_texts:
            assert validate_message_text(text) == False
    
    def test_custom_length_limit(self):
        """Test custom length limits."""
        long_text = "A" * 100
        assert validate_message_text(long_text, max_length=50) == False
        assert validate_message_text(long_text, max_length=200) == True


class TestCaptionValidation:
    """Test caption validation."""
    
    def test_valid_captions(self):
        """Test valid caption formats."""
        valid_captions = [
            "",  # Empty caption is allowed
            None,  # None is allowed
            "Simple caption",
            "Caption with emoji 📸",
            "A" * 1023,  # Just under limit
        ]
        
        for caption in valid_captions:
            assert validate_caption(caption) == True
    
    def test_invalid_captions(self):
        """Test invalid caption formats."""
        invalid_captions = [
            123,  # Not a string
            "A" * 1025,  # Over limit
        ]
        
        for caption in invalid_captions:
            assert validate_caption(caption) == False


class TestLocationValidation:
    """Test location name and address validation."""
    
    def test_valid_location_names(self):
        """Test valid location names."""
        valid_names = [
            "",  # Empty allowed
            None,  # None allowed
            "Jounieh, Lebanon",
            "A" * 999,  # Just under limit
        ]
        
        for name in valid_names:
            assert validate_location_name(name) == True
    
    def test_invalid_location_names(self):
        """Test invalid location names."""
        invalid_names = [
            123,  # Not a string
            "A" * 1001,  # Over limit
        ]
        
        for name in invalid_names:
            assert validate_location_name(name) == False
    
    def test_valid_location_addresses(self):
        """Test valid location addresses."""
        valid_addresses = [
            "",  # Empty allowed
            None,  # None allowed
            "Jounieh, Mount Lebanon Governorate, Lebanon",
            "A" * 999,  # Just under limit
        ]
        
        for address in valid_addresses:
            assert validate_location_address(address) == True
    
    def test_invalid_location_addresses(self):
        """Test invalid location addresses."""
        invalid_addresses = [
            123,  # Not a string
            "A" * 1001,  # Over limit
        ]
        
        for address in invalid_addresses:
            assert validate_location_address(address) == False


class TestTemplateValidation:
    """Test template validation."""
    
    def test_valid_template_names(self):
        """Test valid template names."""
        valid_names = [
            "swiftreplies_introduction",
            "welcome_message",
            "test-template",
            "template123",
            "UPPERCASE_TEMPLATE",
        ]
        
        for name in valid_names:
            assert validate_template_name(name) == True
    
    def test_invalid_template_names(self):
        """Test invalid template names."""
        invalid_names = [
            "",
            None,
            "template with spaces",
            "template@special",
            "template.dot",
            123,
        ]
        
        for name in invalid_names:
            assert validate_template_name(name) == False
    
    def test_valid_template_variables(self):
        """Test valid template variables."""
        valid_variables = [
            None,  # None allowed
            [],    # Empty list allowed
            ["antonio"],
            ["name", "date", "time"],
            ["var1", "var2", "var3", "var4", "var5"],  # Within limit
        ]
        
        for variables in valid_variables:
            assert validate_template_variables(variables) == True
    
    def test_invalid_template_variables(self):
        """Test invalid template variables."""
        invalid_variables = [
            "not_a_list",
            [123, "string"],  # Mixed types
            ["valid", None, "also_valid"],  # None in list
            ["var" + str(i) for i in range(15)],  # Too many variables
        ]
        
        for variables in invalid_variables:
            assert validate_template_variables(variables) == False


class TestFileSizeValidation:
    """Test file size validation."""
    
    def test_valid_file_sizes(self):
        """Test valid file sizes."""
        valid_sizes = [
            (1024, "image"),           # 1KB image
            (5 * 1024 * 1024, "image"), # 5MB image (at limit)
            (16 * 1024 * 1024, "video"), # 16MB video (at limit)
            (0, "image"),              # Zero size (edge case)
        ]
        
        for size, media_type in valid_sizes:
            assert validate_file_size(size, media_type) == True
    
    def test_invalid_file_sizes(self):
        """Test invalid file sizes."""
        invalid_sizes = [
            (-1, "image"),              # Negative size
            (6 * 1024 * 1024, "image"), # Over 5MB limit for image
            (17 * 1024 * 1024, "video"), # Over 16MB limit for video
        ]
        
        for size, media_type in invalid_sizes:
            assert validate_file_size(size, media_type) == False


class TestContentTypeValidation:
    """Test content type validation."""
    
    def test_valid_content_types(self):
        """Test valid content types."""
        valid_types = [
            "image/jpeg",
            "image/png", 
            "image/webp",
            "video/mp4",
            "audio/mpeg",
            "application/pdf",
        ]
        
        for content_type in valid_types:
            assert validate_content_type(content_type) == True
    
    def test_invalid_content_types(self):
        """Test invalid content types."""
        invalid_types = [
            "",
            None,
            "text/html",  # Not supported
            "application/exe",  # Not supported
            "image/bmp",  # Not supported
        ]
        
        for content_type in invalid_types:
            assert validate_content_type(content_type) == False


class TestMessageIdValidation:
    """Test message ID validation."""
    
    def test_valid_message_ids(self):
        """Test valid message ID formats."""
        valid_ids = [
            "1e5671ed-062d-49cf-81b5-3fdb7d73ed5e",
            "abc123def456",
            "message_id_123",
            "MSG-001",
        ]
        
        for msg_id in valid_ids:
            assert validate_message_id(msg_id) == True
    
    def test_invalid_message_ids(self):
        """Test invalid message ID formats."""
        invalid_ids = [
            "",
            None,
            "id with spaces",
            "id@special.chars",
            123,
        ]
        
        for msg_id in invalid_ids:
            assert validate_message_id(msg_id) == False


class TestLanguageCodeValidation:
    """Test language code validation."""
    
    def test_valid_language_codes(self):
        """Test valid language codes."""
        valid_codes = [
            "en",
            "ar",
            "fr",
            "ES",  # Should handle uppercase
        ]
        
        for code in valid_codes:
            assert validate_language_code(code) == True
    
    def test_invalid_language_codes(self):
        """Test invalid language codes."""
        invalid_codes = [
            "",
            None,
            "eng",  # Too long
            "e",    # Too short
            "en-US", # Too specific
            123,
        ]
        
        for code in invalid_codes:
            assert validate_language_code(code) == False


class TestCombinedValidation:
    """Test combined validation functions."""
    
    def test_validate_all_message_params_valid(self):
        """Test all message parameters validation with valid inputs."""
        is_valid, errors = validate_all_message_params(
            to_number="+96170895652",
            message_content="Hello world!",
            media_url="https://example.com/image.jpg",
            caption="Test caption"
        )
        
        assert is_valid == True
        assert len(errors) == 0
    
    def test_validate_all_message_params_invalid(self):
        """Test all message parameters validation with invalid inputs."""
        is_valid, errors = validate_all_message_params(
            to_number="invalid_phone",
            message_content="",  # Empty message
            media_url="not_a_url",
            caption="A" * 2000  # Too long caption
        )
        
        assert is_valid == False
        assert len(errors) > 0
    
    def test_validate_location_params_valid(self):
        """Test location parameters validation with valid inputs."""
        is_valid, errors = validate_location_params(
            latitude=33.983333,
            longitude=35.633333,
            name="Jounieh, Lebanon",
            address="Jounieh, Mount Lebanon Governorate, Lebanon"
        )
        
        assert is_valid == True
        assert len(errors) == 0
    
    def test_validate_location_params_invalid(self):
        """Test location parameters validation with invalid inputs."""
        is_valid, errors = validate_location_params(
            latitude=91,  # Invalid latitude
            longitude=-181,  # Invalid longitude
            name="A" * 2000,  # Too long name
            address="A" * 2000  # Too long address
        )
        
        assert is_valid == False
        assert len(errors) > 0


class TestStrictValidation:
    """Test strict validation mode across different functions."""
    
    def test_strict_mode_raises_exceptions(self):
        """Test that strict mode raises appropriate exceptions."""
        
        # Phone number
        with pytest.raises(ValidationError):
            validate_phone_number("invalid", strict=True)
        
        # Coordinates
        with pytest.raises(ValidationError):
            validate_coordinates(91, 0, strict=True)
        
        # URL
        with pytest.raises(ValidationError):
            validate_url("invalid", strict=True)
        
        # Message text
        with pytest.raises(ValidationError):
            validate_message_text("", strict=True)
        
        # Template name
        with pytest.raises(ValidationError):
            validate_template_name("", strict=True)
    
    def test_strict_mode_passes_valid_inputs(self):
        """Test that strict mode passes for valid inputs."""
        
        # All these should pass without raising exceptions
        assert validate_phone_number("+96170895652", strict=True) == True
        assert validate_coordinates(33.98, 35.63, strict=True) == True
        assert validate_url("https://example.com", strict=True) == True
        assert validate_message_text("Hello", strict=True) == True
        assert validate_template_name("valid_template", strict=True) == True


if __name__ == "__main__":
    pytest.main([__file__]) 