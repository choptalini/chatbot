"""
Unit tests for infobip_whatsapp_methods.client module.

Tests all WhatsAppClient functionality including message sending, media handling,
auto-responses, and error handling scenarios.
"""

import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
import json
import sys
import os
import requests

# Add the parent directory to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from infobip_whatsapp_methods.client import WhatsAppClient
from infobip_whatsapp_methods.models import (
    MessageResponse,
    MediaMetadataResponse,
    MediaDownloadResponse,
    StatusResponse,
    AutoResponseResult
)
from infobip_whatsapp_methods.exceptions import (
    AuthenticationError,
    ValidationError,
    NetworkError,
    APIError
)


class TestWhatsAppClientInitialization:
    """Test client initialization and configuration."""
    
    def test_client_initialization_with_parameters(self):
        """Test successful client initialization with explicit parameters."""
        client = WhatsAppClient(
            api_key="test_api_key",
            base_url="test.api.infobip.com",
            sender="96179374241"
        )
        
        assert client.api_key == "test_api_key"
        assert client.base_url == "https://test.api.infobip.com"
        assert client.sender == "96179374241"
        assert client.timeout == 30
        assert client.retry_attempts == 3
    
    @patch.dict(os.environ, {
        "INFOBIP_API_KEY": "env_api_key",
        "INFOBIP_BASE_URL": "env.api.infobip.com",
        "WHATSAPP_SENDER": "96179374241"
    })
    def test_client_initialization_with_env_vars(self):
        """Test client initialization using environment variables."""
        client = WhatsAppClient()
        
        assert client.api_key == "env_api_key"
        assert client.base_url == "https://env.api.infobip.com"
        assert client.sender == "96179374241"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_client_initialization_missing_credentials(self):
        """Test that initialization fails with missing credentials."""
        with pytest.raises(AuthenticationError):
            WhatsAppClient()
        
        with pytest.raises(AuthenticationError):
            WhatsAppClient(api_key="test", base_url="test.com")  # Missing sender
    
    def test_base_url_normalization(self):
        """Test that base URLs are properly normalized."""
        # Without protocol
        client = WhatsAppClient(
            api_key="test",
            base_url="api.infobip.com",
            sender="96179374241"
        )
        assert client.base_url == "https://api.infobip.com"
        
        # With https protocol
        client = WhatsAppClient(
            api_key="test",
            base_url="https://api.infobip.com/",
            sender="96179374241"
        )
        assert client.base_url == "https://api.infobip.com"


class TestTextMessaging:
    """Test text message functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return WhatsAppClient(
            api_key="test_api_key",
            base_url="test.api.infobip.com",
            sender="96179374241"
        )
    
    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_send_text_message_success(self, mock_request, client):
        """Test successful text message sending."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "messages": [{"messageId": "test_message_id_123"}]
        }
        mock_response.headers = {}
        mock_request.return_value = mock_response
        
        # Send message
        response = client.send_text_message("96170895652", "Hello, world!")
        
        # Verify response
        assert response.success == True
        assert response.message_id == "test_message_id_123"
        assert response.metadata["to_number"] == "96170895652"
        assert response.metadata["message_length"] == 13
        
        # Verify API call
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["json"]["to"] == "96170895652"
        assert call_kwargs["json"]["content"]["text"] == "Hello, world!"
    
    def test_send_text_message_validation_error(self, client):
        """Test text message validation errors."""
        # Invalid phone number
        with pytest.raises(ValidationError):
            client.send_text_message("invalid", "Hello")
        
        # Empty message
        with pytest.raises(ValidationError):
            client.send_text_message("96170895652", "")
        
        # Message too long
        with pytest.raises(ValidationError):
            client.send_text_message("96170895652", "A" * 5000)
    
    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_send_text_message_api_error(self, mock_request, client):
        """Test text message API error handling."""
        # Mock API error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"requestError": {"serviceException": {"text": "Invalid phone number"}}}
        mock_request.return_value = mock_response
        
        # Should raise ValidationError for 400 status
        with pytest.raises(ValidationError):
            client.send_text_message("96170895652", "Hello")

    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_send_text_message_with_emojis(self, mock_request, client):
        """Test sending a text message with emojis."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messages": [{"messageId": "emoji_msg_123"}]}
        mock_response.headers = {}
        mock_request.return_value = mock_response
        
        message = "Hello with an emoji 😊!"
        response = client.send_text_message("96170895652", message)
        
        assert response.success
        assert response.message_id == "emoji_msg_123"
        
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["json"]["content"]["text"] == message

    def test_send_text_message_empty_number(self, client):
        """Test sending a text message to an empty number."""
        with pytest.raises(ValidationError):
            client.send_text_message("", "Hello")

    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_send_text_message_unexpected_error(self, mock_request, client):
        """Test handling of unexpected errors during text message sending."""
        mock_request.side_effect = Exception("Something went wrong")
        
        response = client.send_text_message("96170895652", "Hello")
        
        assert not response.success
        assert "Unexpected error" in response.error


class TestImageMessaging:
    """Test image message functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return WhatsAppClient(
            api_key="test_api_key",
            base_url="test.api.infobip.com",
            sender="96179374241"
        )
    
    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_send_image_success(self, mock_request, client):
        """Test successful image sending."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messageId": "img_message_123"}
        mock_response.headers = {}
        mock_request.return_value = mock_response
        
        # Send image
        response = client.send_image(
            "96170895652",
            "https://example.com/image.jpg",
            "Check this out!"
        )
        
        # Verify response
        assert response.success == True
        assert response.message_id == "img_message_123"
        assert response.metadata["image_url"] == "https://example.com/image.jpg"
        assert response.metadata["caption"] == "Check this out!"
    
    def test_send_image_validation_error(self, client):
        """Test image validation errors."""
        # Invalid URL
        with pytest.raises(ValidationError):
            client.send_image("96170895652", "not_a_url")
        
        # HTTP URL (should require HTTPS)
        with pytest.raises(ValidationError):
            client.send_image("96170895652", "http://example.com/image.jpg")
        
        # Caption too long
        with pytest.raises(ValidationError):
            client.send_image(
                "96170895652",
                "https://example.com/image.jpg",
                "A" * 2000
            )

    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_send_image_no_caption(self, mock_request, client):
        """Test sending an image without a caption."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messageId": "no_caption_img_123"}
        mock_response.headers = {}
        mock_request.return_value = mock_response
        
        response = client.send_image("96170895652", "https://example.com/image.jpg")
        
        assert response.success
        assert "caption" not in mock_request.call_args[1]["json"]["content"]

    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_send_image_api_error(self, mock_request, client):
        """Test API error handling when sending an image."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"requestError": {"serviceException": {"text": "Invalid image URL"}}}
        mock_request.return_value = mock_response
        
        with pytest.raises(ValidationError):
            client.send_image("96170895652", "https://example.com/invalid.jpg")


class TestLocationMessaging:
    """Test location message functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return WhatsAppClient(
            api_key="test_api_key",
            base_url="test.api.infobip.com",
            sender="96179374241"
        )
    
    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_send_location_success(self, mock_request, client):
        """Test successful location sending."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messageId": "loc_message_123"}
        mock_response.headers = {}
        mock_request.return_value = mock_response
        
        # Send location
        response = client.send_location(
            "96170895652",
            33.983333,
            35.633333,
            "Jounieh, Lebanon",
            "Jounieh, Mount Lebanon Governorate, Lebanon"
        )
        
        # Verify response
        assert response.success == True
        assert response.message_id == "loc_message_123"
        assert response.metadata["coordinates"]["latitude"] == 33.983333
        assert response.metadata["coordinates"]["longitude"] == 35.633333
        assert response.metadata["name"] == "Jounieh, Lebanon"
    
    def test_send_location_validation_error(self, client):
        """Test location validation errors."""
        # Invalid coordinates
        with pytest.raises(ValidationError):
            client.send_location("96170895652", 91, 0)  # Latitude too high
        
        with pytest.raises(ValidationError):
            client.send_location("96170895652", 0, 181)  # Longitude too high
    
    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_send_location_preset_success(self, mock_request, client):
        """Test sending preset location."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messageId": "preset_loc_123"}
        mock_response.headers = {}
        mock_request.return_value = mock_response
        
        # Send preset location
        response = client.send_location_preset("96170895652", "jounieh")
        
        # Verify response
        assert response.success == True
        assert response.message_id == "preset_loc_123"
    
    def test_send_location_preset_invalid(self, client):
        """Test invalid preset location."""
        with pytest.raises(ValidationError):
            client.send_location_preset("96170895652", "unknown_location")

    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_send_location_api_error(self, mock_request, client):
        """Test API error handling when sending a location."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"requestError": {"serviceException": {"text": "Invalid coordinates"}}}
        mock_request.return_value = mock_response
        
        with pytest.raises(ValidationError):
            client.send_location("96170895652", 0, 0)


class TestTemplateMessaging:
    """Test template message functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return WhatsAppClient(
            api_key="test_api_key",
            base_url="test.api.infobip.com",
            sender="96179374241"
        )
    
    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_send_template_success(self, mock_request, client):
        """Test successful template sending."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "messages": [{"messageId": "template_msg_123"}]
        }
        mock_response.headers = {}
        mock_request.return_value = mock_response
        
        # Send template
        response = client.send_template(
            "96170895652",
            "swiftreplies_introduction",
            variables=["Antonio"],
            buttons=[{"type": "QUICK_REPLY", "parameter": "get_started"}]
        )
        
        # Verify response
        assert response.success == True
        assert response.message_id == "template_msg_123"
        assert response.metadata["template_name"] == "swiftreplies_introduction"
        assert response.metadata["variables"] == ["Antonio"]
    
    def test_send_template_validation_error(self, client):
        """Test template validation errors."""
        # Invalid template name
        with pytest.raises(ValidationError):
            client.send_template("96170895652", "invalid template name")
        
        # Too many variables
        with pytest.raises(ValidationError):
            client.send_template(
                "96170895652",
                "test_template",
                variables=["var" + str(i) for i in range(15)]
            )

    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_send_template_api_error(self, mock_request, client):
        """Test API error handling when sending a template."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"requestError": {"serviceException": {"text": "Template not found"}}}
        mock_request.return_value = mock_response
        
        with pytest.raises(ValidationError):
            client.send_template("96170895652", "non_existent_template")


class TestMediaHandling:
    """Test media download and metadata functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return WhatsAppClient(
            api_key="test_api_key",
            base_url="test.api.infobip.com",
            sender="96179374241"
        )
    
    @patch('infobip_whatsapp_methods.client.requests.head')
    def test_get_media_metadata_success(self, mock_head, client):
        """Test successful media metadata retrieval."""
        # Mock successful HEAD response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "image/jpeg",
            "content-length": "1024000",
            "last-modified": "Wed, 21 Oct 2015 07:28:00 GMT"
        }
        mock_head.return_value = mock_response
        
        # Get metadata
        metadata = client.get_media_metadata("https://example.com/image.jpg")
        
        # Verify response
        assert metadata.success == True
        assert metadata.content_type == "image/jpeg"
        assert metadata.content_length == 1024000
        assert abs(metadata.file_size_mb - 0.98) < 0.01  # Allow for rounding differences
        assert metadata.is_image == True
    
    @patch('infobip_whatsapp_methods.client.requests.head')
    def test_get_media_metadata_error(self, mock_head, client):
        """Test media metadata error handling."""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_head.return_value = mock_response
        
        # Get metadata
        metadata = client.get_media_metadata("https://example.com/missing.jpg")
        
        # Verify error response
        assert metadata.success == False
        assert "404" in metadata.error

    @patch('infobip_whatsapp_methods.client.requests.head')
    def test_get_media_metadata_network_error(self, mock_head, client):
        """Test network error during metadata retrieval."""
        mock_head.side_effect = requests.exceptions.ConnectionError
        
        metadata = client.get_media_metadata("https://example.com/image.jpg")
        
        assert not metadata.success
        assert "Request failed" in metadata.error

    @patch('infobip_whatsapp_methods.client.requests.get')
    @patch('infobip_whatsapp_methods.client.requests.head')
    @patch('builtins.open', new_callable=mock_open)
    def test_download_media_success(self, mock_file, mock_head, mock_get, client):
        """Test successful media download."""
        # Mock HEAD response for metadata
        mock_head_response = Mock()
        mock_head_response.status_code = 200
        mock_head_response.headers = {
            "content-type": "image/jpeg",
            "content-length": "1024"
        }
        mock_head.return_value = mock_head_response
        
        # Mock GET response for download
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.iter_content.return_value = [b"fake_image_data"]
        mock_get.return_value = mock_get_response
        
        # Mock file stat and Path.mkdir
        with patch('pathlib.Path.stat') as mock_stat, \
             patch('pathlib.Path.mkdir'), \
             patch('pathlib.Path.__truediv__') as mock_div:
            
            mock_stat.return_value.st_size = 1024
            
            # Mock the file path operations
            mock_file_path = Mock()
            mock_file_path.stat.return_value.st_size = 1024
            mock_div.return_value = mock_file_path
            
            # Download media
            result = client.download_media("https://example.com/image.jpg")
        
        # Verify result
        assert result.success == True
        assert result.file_size == 1024
        assert result.content_type == "image/jpeg"
        assert "image.jpg" in result.filename

    @patch('infobip_whatsapp_methods.client.requests.head')
    def test_download_media_metadata_failed(self, mock_head, client):
        """Test media download when metadata retrieval fails."""
        mock_head.return_value.status_code = 404
        
        result = client.download_media("https://example.com/missing.jpg")
        
        assert not result.success
        assert "Failed to get metadata" in result.error

    @patch('infobip_whatsapp_methods.client.requests.get')
    @patch('infobip_whatsapp_methods.client.requests.head')
    def test_download_media_download_failed(self, mock_head, mock_get, client):
        """Test media download when the download itself fails."""
        mock_head.return_value.status_code = 200
        mock_head.return_value.headers = {"content-type": "image/jpeg"}
        
        mock_get.return_value.status_code = 500
        
        result = client.download_media("https://example.com/server_error.jpg")
        
        assert not result.success
        assert "Download failed" in result.error


class TestStatusOperations:
    """Test message status operations."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return WhatsAppClient(
            api_key="test_api_key",
            base_url="test.api.infobip.com",
            sender="96179374241"
        )
    
    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_mark_as_read_success(self, mock_request, client):
        """Test successful message read marking."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "READ"}
        mock_response.headers = {}
        mock_request.return_value = mock_response
        
        # Mark as read
        response = client.mark_as_read("test_message_id")
        
        # Verify response
        assert response.success == True
        assert response.message_id == "test_message_id"
        assert response.status == "READ"
    
    def test_mark_as_read_validation_error(self, client):
        """Test mark as read validation error."""
        # Invalid message ID
        with pytest.raises(ValidationError):
            client.mark_as_read("")

    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_mark_as_read_api_error(self, mock_request, client):
        """Test API error handling when marking a message as read."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"requestError": {"serviceException": {"text": "Invalid message ID"}}}
        mock_request.return_value = mock_response
        
        with pytest.raises(ValidationError):
            client.mark_as_read("invalid_message_id")


class TestAutoResponse:
    """Test auto-response functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return WhatsAppClient(
            api_key="test_api_key",
            base_url="test.api.infobip.com",
            sender="96179374241"
        )
    
    def test_auto_respond_keyword_match(self, client):
        """Test auto-response with keyword matching."""
        # Test without sending
        result = client.auto_respond(
            "Hey there!",
            sender_name="Antonio",
            send_response=False
        )
        
        # Verify result
        assert result.success == True
        assert "Antonio" in result.response_text
        assert result.response_type == "keyword_match"
        assert result.message_sent == False
    
    def test_auto_respond_default_response(self, client):
        """Test auto-response with default template."""
        # Test with unknown keyword
        result = client.auto_respond(
            "Some random message",
            sender_name="Antonio",
            send_response=False
        )
        
        # Verify result
        assert result.success == True
        assert "Antonio" in result.response_text
        assert "Some random message" in result.response_text
        assert result.response_type == "default"
    
    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_auto_respond_with_sending(self, mock_request, client):
        """Test auto-response with actual message sending."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "messages": [{"messageId": "auto_response_123"}]
        }
        mock_response.headers = {}
        mock_request.return_value = mock_response
        
        # Auto-respond with sending
        result = client.auto_respond(
            "Hello",
            sender_name="Antonio",
            sender_number="96170895652",
            send_response=True
        )
        
        # Verify result
        assert result.success == True
        assert result.message_sent == True
        assert result.message_id == "auto_response_123"
    
    def test_auto_respond_custom_templates(self, client):
        """Test auto-response with custom templates."""
        custom_templates = {
            "test": "This is a test response for {name}!"
        }
        
        result = client.auto_respond(
            "test message",
            sender_name="Antonio",
            custom_templates=custom_templates,
            send_response=False
        )
        
        assert "This is a test response for Antonio!" == result.response_text

    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_auto_respond_send_failure(self, mock_request, client):
        """Test auto-response when message sending fails."""
        mock_request.side_effect = APIError("Failed to send")
        
        result = client.auto_respond(
            "Hello",
            sender_name="Antonio",
            sender_number="96170895652",
            send_response=True
        )
        
        assert not result.success
        assert result.message_sent == False
        assert "Failed to send response" in result.error


class TestWebhookHelpers:
    """Test webhook helper functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return WhatsAppClient(
            api_key="test_api_key",
            base_url="test.api.infobip.com",
            sender="96179374241"
        )
    
    def test_parse_webhook_payload_text_message(self, client):
        """Test parsing a webhook payload for a text message."""
        payload = {
            "results": [
                {
                    "messageId": "webhook_msg_1",
                    "from": "96170123456",
                    "to": "96179374241",
                    "receivedAt": "2024-01-01T12:00:00.000Z",
                    "message": {
                        "text": "Hello from webhook!",
                        "type": "TEXT"
                    },
                    "contact": {"name": "Webhook Tester"}
                }
            ]
        }
        
        messages = client.parse_webhook_payload(payload)
        
        assert len(messages) == 1
        message = messages[0]
        
        assert message.message_id == "webhook_msg_1"
        assert message.from_number == "96170123456"
        assert message.message_type == "text"
        assert message.text == "Hello from webhook!"
        assert message.contact_name == "Webhook Tester"
        
    def test_parse_webhook_payload_image_message(self, client):
        """Test parsing a webhook payload for an image message."""
        payload = {
            "results": [
                {
                    "messageId": "webhook_msg_2",
                    "from": "96170123456",
                    "to": "96179374241",
                    "receivedAt": "2024-01-01T12:05:00.000Z",
                    "message": {
                        "url": "https://example.com/webhook_image.jpg",
                        "caption": "Image from webhook",
                        "type": "IMAGE"
                    },
                    "contact": {"name": "Webhook Tester"}
                }
            ]
        }
        
        messages = client.parse_webhook_payload(payload)
        
        assert len(messages) == 1
        message = messages[0]
        
        assert message.message_type == "image"
        assert message.media_url == "https://example.com/webhook_image.jpg"
        
    def test_parse_webhook_payload_empty(self, client):
        """Test parsing an empty or invalid webhook payload."""
        assert client.parse_webhook_payload({}) == []
        assert client.parse_webhook_payload({"results": []}) == []
        assert client.parse_webhook_payload({"some_other_key": []}) == []


class TestErrorHandling:
    """Test error handling and retry logic."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return WhatsAppClient(
            api_key="test_api_key",
            base_url="test.api.infobip.com",
            sender="96179374241",
            retry_attempts=2
        )
    
    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_network_error_retry(self, mock_request, client):
        """Test network error retry logic."""
        # First two calls fail, third succeeds
        mock_request.side_effect = [
            requests.exceptions.ConnectionError("Connection failed"),
            requests.exceptions.ConnectionError("Connection failed"),
            Mock(status_code=200, json=lambda: {"messages": [{"messageId": "123"}]}, headers={})
        ]
        
        # Should succeed after retries
        response = client.send_text_message("96170895652", "Hello")
        assert response.success == True
        assert mock_request.call_count == 3
    
    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_rate_limit_retry(self, mock_request, client):
        """Test rate limit retry logic."""
        # Mock rate limit response then success
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"Retry-After": "1"}
        
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"messages": [{"messageId": "123"}]}
        success_response.headers = {}
        
        mock_request.side_effect = [rate_limit_response, success_response]
        
        # Should succeed after rate limit retry
        with patch('time.sleep'):  # Mock sleep to speed up test
            response = client.send_text_message("96170895652", "Hello")
            assert response.success == True


class TestClientConfiguration:
    """Test client configuration and utility methods."""
    
    def test_get_client_info(self):
        """Test client info retrieval."""
        client = WhatsAppClient(
            api_key="test_api_key",
            base_url="test.api.infobip.com",
            sender="96179374241"
        )
        
        info = client.get_client_info()
        
        assert info["sender"] == "96179374241"
        assert info["base_url"] == "https://test.api.infobip.com"
        assert info["timeout"] == 30
        assert info["retry_attempts"] == 3
        assert "available_presets" in info
        assert "jounieh" in info["available_presets"]
    
    @patch('infobip_whatsapp_methods.client.requests.request')
    def test_validation_toggle(self, mock_request):
        """Test validation enable/disable."""
        # Mock successful API response to prevent real API calls
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messages": [{"messageId": "test_123"}]}
        mock_response.headers = {}
        mock_request.return_value = mock_response
        
        # Client with validation disabled
        client = WhatsAppClient(
            api_key="test_api_key",
            base_url="test.api.infobip.com",
            sender="96179374241",
            enable_validation=False
        )
        
        # Should not raise validation error for invalid input
        # (validation is explicitly disabled)
        try:
            result = client.send_text_message("invalid_phone", "Hello", validate_input=False)
            # If no validation exception was raised, test passes
            assert result.success == True
        except ValidationError:
            pytest.fail("Validation should be disabled")


if __name__ == "__main__":
    pytest.main([__file__]) 