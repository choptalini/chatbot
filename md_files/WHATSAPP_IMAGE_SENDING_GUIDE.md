# 📸 WhatsApp Image Sending with Infobip API

## ✅ Success! Image Sent

**Message ID**: `a19ab38d-851f-40ca-bb9f-ac932c72c68e`  
**Status**: PENDING_ENROUTE  
**Recipient**: antonio (96170895652)  
**Image**: Bionic robot image from Shopify CDN

## 🖼️ Overview

The Infobip WhatsApp Business API supports sending various media types including images, documents, videos, and audio files. This guide focuses on image sending capabilities.

## 📋 Prerequisites

- ✅ **Infobip Account** with WhatsApp Business API access
- ✅ **API Key** and Base URL from Infobip
- ✅ **WhatsApp Business Number** (sender)
- ✅ **24-hour messaging window** or approved template

## 🔧 API Endpoint

### Image Message Endpoint
```
POST https://{base_url}/whatsapp/1/message/image
```

### Headers Required
```http
Authorization: App {your_api_key}
Content-Type: application/json
Accept: application/json
```

## 📦 Request Payload Structure

### Basic Image Message
```json
{
  "from": "96179374241",
  "to": "96170895652",
  "content": {
    "mediaUrl": "https://example.com/image.jpg"
  }
}
```

### Image Message with Caption
```json
{
  "from": "96179374241",
  "to": "96170895652",
  "content": {
    "mediaUrl": "https://example.com/image.jpg",
    "caption": "🖼️ Your image caption here"
  }
}
```

## 🎯 Implementation Examples

### Python Example (Using Requests)
```python
import requests

def send_whatsapp_image(api_key, base_url, sender, recipient, image_url, caption=""):
    endpoint = f"https://{base_url}/whatsapp/1/message/image"
    
    headers = {
        "Authorization": f"App {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "from": sender,
        "to": recipient,
        "content": {
            "mediaUrl": image_url
        }
    }
    
    if caption:
        payload["content"]["caption"] = caption
    
    response = requests.post(endpoint, json=payload, headers=headers)
    return response.json()

# Usage
result = send_whatsapp_image(
    api_key="your_api_key",
    base_url="your_base_url",
    sender="96179374241",
    recipient="96170895652",
    image_url="https://example.com/image.jpg",
    caption="🖼️ Check out this image!"
)
```

### JavaScript/Node.js Example
```javascript
const axios = require('axios');

async function sendWhatsAppImage(apiKey, baseUrl, sender, recipient, imageUrl, caption = '') {
    const endpoint = `https://${baseUrl}/whatsapp/1/message/image`;
    
    const headers = {
        'Authorization': `App ${apiKey}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    };
    
    const payload = {
        from: sender,
        to: recipient,
        content: {
            mediaUrl: imageUrl
        }
    };
    
    if (caption) {
        payload.content.caption = caption;
    }
    
    try {
        const response = await axios.post(endpoint, payload, { headers });
        return response.data;
    } catch (error) {
        console.error('Error sending image:', error.response?.data || error.message);
        throw error;
    }
}

// Usage
sendWhatsAppImage(
    'your_api_key',
    'your_base_url',
    '96179374241',
    '96170895652',
    'https://example.com/image.jpg',
    '🖼️ Check out this image!'
);
```

### cURL Example
```bash
curl -X POST "https://your_base_url/whatsapp/1/message/image" \
  -H "Authorization: App your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "96179374241",
    "to": "96170895652",
    "content": {
      "mediaUrl": "https://example.com/image.jpg",
      "caption": "🖼️ Your image caption"
    }
  }'
```

## 📊 Response Format

### Successful Response (200 OK)
```json
{
  "to": "96170895652",
  "messageCount": 1,
  "messageId": "a19ab38d-851f-40ca-bb9f-ac932c72c68e",
  "status": {
    "groupId": 1,
    "groupName": "PENDING",
    "id": 7,
    "name": "PENDING_ENROUTE",
    "description": "Message sent to next instance"
  }
}
```

### Error Response (4xx/5xx)
```json
{
  "requestError": {
    "serviceException": {
      "messageId": "BAD_REQUEST",
      "text": "Bad request",
      "validationErrors": [
        {
          "field": "content.mediaUrl",
          "message": "Invalid media URL"
        }
      ]
    }
  }
}
```

## 🖼️ Supported Image Formats

| Format | Extension | Max Size | Notes |
|--------|-----------|----------|-------|
| JPEG | .jpg, .jpeg | 5 MB | Most common, good compression |
| PNG | .png | 5 MB | Supports transparency |
| WebP | .webp | 5 MB | Modern format, good compression |
| GIF | .gif | 5 MB | Supports animation |

## 📏 Image Requirements

### Technical Specifications
- **Maximum file size**: 5 MB
- **Minimum dimensions**: 100x100 pixels
- **Maximum dimensions**: 4096x4096 pixels
- **Aspect ratio**: Any (recommended 16:9 or 1:1)

### URL Requirements
- ✅ **HTTPS required** (HTTP not supported)
- ✅ **Publicly accessible** (no authentication required)
- ✅ **Direct file URL** (not a webpage containing image)
- ✅ **Proper MIME type** headers
- ✅ **Stable URL** (doesn't expire quickly)

## 🎨 Best Practices

### Image Optimization
1. **Compress images** to reduce file size while maintaining quality
2. **Use appropriate dimensions** (avoid unnecessarily large images)
3. **Choose right format**: JPEG for photos, PNG for graphics with transparency
4. **Test image URLs** before sending to ensure accessibility

### Caption Guidelines
- **Maximum length**: 4096 characters
- **Use emojis** to make captions more engaging
- **Include context** about the image
- **Add call-to-action** if appropriate

### Error Handling
```python
def send_image_with_retry(image_url, recipient, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = send_whatsapp_image(
                api_key=API_KEY,
                base_url=BASE_URL,
                sender=SENDER,
                recipient=recipient,
                image_url=image_url
            )
            
            if result.get('messageId'):
                return result
            else:
                print(f"Attempt {attempt + 1} failed: {result}")
                
        except Exception as e:
            print(f"Attempt {attempt + 1} error: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
```

## 🔍 Common Issues & Solutions

### 1. Image Not Loading
**Problem**: Image appears as broken/not loading in WhatsApp
```
❌ Error: "Media download failed"
```

**Solutions**:
- ✅ Verify image URL is publicly accessible
- ✅ Check HTTPS (not HTTP) protocol
- ✅ Ensure image size is under 5MB
- ✅ Verify correct MIME type headers

**Test your URL**:
```bash
curl -I "https://your-image-url.jpg"
# Should return 200 OK with image/jpeg content-type
```

### 2. Invalid Media URL Error
**Problem**: API returns validation error
```json
{
  "field": "content.mediaUrl",
  "message": "Invalid media URL"
}
```

**Solutions**:
- ✅ URL must start with `https://`
- ✅ URL must point directly to image file
- ✅ Remove any query parameters that might interfere
- ✅ Use URL encoding for special characters

### 3. File Size Too Large
**Problem**: Image exceeds 5MB limit
```
❌ Error: "Media file too large"
```

**Solutions**:
```python
from PIL import Image
import io

def compress_image_url(image_url, max_size_mb=4):
    """Download and compress image if needed"""
    response = requests.get(image_url)
    img = Image.open(io.BytesIO(response.content))
    
    # Calculate compression ratio
    current_size_mb = len(response.content) / (1024 * 1024)
    if current_size_mb <= max_size_mb:
        return image_url
    
    # Compress image
    quality = int(85 * (max_size_mb / current_size_mb))
    
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=quality, optimize=True)
    
    # Upload compressed image to your server and return new URL
    return upload_compressed_image(output.getvalue())
```

## 🚀 Advanced Features

### 1. Image Validation Before Sending
```python
import requests
from PIL import Image
import io

def validate_image_url(image_url):
    """Validate image URL before sending"""
    try:
        # Check if URL is accessible
        response = requests.head(image_url, timeout=10)
        if response.status_code != 200:
            return False, f"URL not accessible: {response.status_code}"
        
        # Check content type
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            return False, f"Invalid content type: {content_type}"
        
        # Check file size
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > 5 * 1024 * 1024:
            return False, "File size exceeds 5MB limit"
        
        return True, "Valid image URL"
        
    except Exception as e:
        return False, f"Validation error: {e}"

# Usage
is_valid, message = validate_image_url(image_url)
if is_valid:
    send_whatsapp_image(...)
else:
    print(f"Image validation failed: {message}")
```

### 2. Batch Image Sending
```python
def send_multiple_images(recipients, image_urls, caption=""):
    """Send same image to multiple recipients"""
    results = []
    
    for recipient in recipients:
        for image_url in image_urls:
            try:
                result = send_whatsapp_image(
                    api_key=API_KEY,
                    base_url=BASE_URL,
                    sender=SENDER,
                    recipient=recipient,
                    image_url=image_url,
                    caption=caption
                )
                results.append({
                    'recipient': recipient,
                    'image_url': image_url,
                    'success': True,
                    'message_id': result.get('messageId'),
                    'result': result
                })
            except Exception as e:
                results.append({
                    'recipient': recipient,
                    'image_url': image_url,
                    'success': False,
                    'error': str(e)
                })
    
    return results
```

## 🔗 Related Media Types

### Document Sending
```bash
POST /whatsapp/1/message/document
{
  "from": "sender",
  "to": "recipient",
  "content": {
    "mediaUrl": "https://example.com/document.pdf",
    "caption": "Document title",
    "filename": "document.pdf"
  }
}
```

### Video Sending
```bash
POST /whatsapp/1/message/video
{
  "from": "sender",
  "to": "recipient", 
  "content": {
    "mediaUrl": "https://example.com/video.mp4",
    "caption": "Video caption"
  }
}
```

### Audio Sending
```bash
POST /whatsapp/1/message/audio
{
  "from": "sender",
  "to": "recipient",
  "content": {
    "mediaUrl": "https://example.com/audio.mp3"
  }
}
```

## 🎯 Quick Reference

### Image Sending Checklist
- [ ] Image URL starts with `https://`
- [ ] Image is publicly accessible (test with curl)
- [ ] Image size is under 5MB
- [ ] Image format is supported (JPEG, PNG, WebP, GIF)
- [ ] Caption is under 4096 characters
- [ ] Within 24-hour messaging window or using approved template
- [ ] API credentials are correct
- [ ] Error handling is implemented

### Status Codes
| Code | Status | Description |
|------|--------|-------------|
| 200 | Success | Image sent successfully |
| 400 | Bad Request | Invalid payload or parameters |
| 401 | Unauthorized | Invalid API key |
| 403 | Forbidden | Access denied or rate limited |
| 404 | Not Found | Endpoint not found |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Server Error | Infobip server error |

## 🎉 Example Success: Bionic Image

**✅ Successfully sent bionic image to antonio!**

- **Image URL**: `https://cdn.shopify.com/s/files/1/0715/1668/4484/files/bionic2_1600x_05ad8cb7-411e-4c1f-8b95-f18c38a331c3.webp?v=1752181116`
- **Message ID**: `a19ab38d-851f-40ca-bb9f-ac932c72c68e`
- **Recipient**: antonio (96170895652)
- **Caption**: "🤖 Check out this cool bionic image! Sent via our WhatsApp API integration."
- **Status**: PENDING_ENROUTE (Successfully queued for delivery)

The image should appear in antonio's WhatsApp within seconds! 📱✨ 