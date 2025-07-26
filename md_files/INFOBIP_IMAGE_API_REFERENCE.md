# 📸 Infobip WhatsApp Image API - Quick Reference

## 🎯 Endpoint
```
POST https://{base_url}/whatsapp/1/message/image
```

## 🔑 Authentication
```http
Authorization: App {your_api_key}
Content-Type: application/json
```

## 📦 Basic Payload
```json
{
  "from": "96179374241",
  "to": "96170895652", 
  "content": {
    "mediaUrl": "https://example.com/image.jpg",
    "caption": "Optional caption text"
  }
}
```

## ✅ Requirements
- **URL**: Must be HTTPS
- **Size**: Max 5MB  
- **Formats**: JPEG, PNG, WebP, GIF
- **Access**: Publicly accessible (no auth required)
- **Caption**: Max 4096 characters

## 🚀 Python Quick Start
```python
import requests

def send_image(api_key, base_url, sender, recipient, image_url, caption=""):
    response = requests.post(
        f"https://{base_url}/whatsapp/1/message/image",
        headers={"Authorization": f"App {api_key}", "Content-Type": "application/json"},
        json={
            "from": sender,
            "to": recipient,
            "content": {"mediaUrl": image_url, "caption": caption}
        }
    )
    return response.json()
```

## 📊 Success Response
```json
{
  "messageId": "a19ab38d-851f-40ca-bb9f-ac932c72c68e",
  "status": {"name": "PENDING_ENROUTE"}
}
```

## ❌ Common Errors
| Error | Solution |
|-------|----------|
| Invalid media URL | Use HTTPS, ensure public access |
| File too large | Compress to under 5MB |
| Bad request | Check payload format |
| Unauthorized | Verify API key |

## 🧪 Test Your Setup
```bash
curl -X POST "https://your_base_url/whatsapp/1/message/image" \
  -H "Authorization: App your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "96179374241",
    "to": "96170895652",
    "content": {
      "mediaUrl": "https://picsum.photos/800/600",
      "caption": "🧪 Test image"
    }
  }'
```

## 🎉 Verified Working Example
**✅ Bionic Image Successfully Sent!**
- **URL**: `https://cdn.shopify.com/s/files/1/0715/1668/4484/files/bionic2_1600x_05ad8cb7-411e-4c1f-8b95-f18c38a331c3.webp?v=1752181116`
- **Message ID**: `a19ab38d-851f-40ca-bb9f-ac932c72c68e`
- **Recipient**: antonio (96170895652)
- **Status**: ✅ PENDING_ENROUTE 