# 📍 Infobip WhatsApp Location API - Quick Reference

## 🎯 Endpoint
```
POST https://{base_url}/whatsapp/1/message/location
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
    "latitude": 33.983333,
    "longitude": 35.633333,
    "name": "Jounieh, Lebanon",
    "address": "Jounieh, Mount Lebanon Governorate, Lebanon"
  }
}
```

## ✅ Requirements
- **Latitude**: -90 to +90 degrees
- **Longitude**: -180 to +180 degrees
- **Name**: Max 1000 characters (optional)
- **Address**: Max 1000 characters (optional)
- **Format**: Decimal degrees (e.g., 33.983333)

## 🚀 Python Quick Start
```python
import requests

def send_location(api_key, base_url, sender, recipient, lat, lon, name="", address=""):
    response = requests.post(
        f"https://{base_url}/whatsapp/1/message/location",
        headers={"Authorization": f"App {api_key}", "Content-Type": "application/json"},
        json={
            "from": sender,
            "to": recipient,
            "content": {
                "latitude": lat,
                "longitude": lon,
                "name": name,
                "address": address
            }
        }
    )
    return response.json()
```

## 📊 Success Response
```json
{
  "messageId": "1e5671ed-062d-49cf-81b5-3fdb7d73ed5e",
  "status": {"name": "PENDING_ENROUTE"}
}
```

## 🗺️ Lebanon Coordinates
```python
locations = {
    "beirut": {"lat": 33.888630, "lon": 35.495480},
    "jounieh": {"lat": 33.983333, "lon": 35.633333},
    "baalbek": {"lat": 34.006667, "lon": 36.204167},
    "tripoli": {"lat": 34.436667, "lon": 35.833333}
}
```

## ❌ Common Errors
| Error | Solution |
|-------|----------|
| Invalid latitude | Use -90 to +90 range |
| Invalid longitude | Use -180 to +180 range |
| Wrong format | Use decimal degrees (33.983333) |
| Unauthorized | Verify API key |

## 🧪 Test Your Setup
```bash
curl -X POST "https://your_base_url/whatsapp/1/message/location" \
  -H "Authorization: App your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "96179374241",
    "to": "96170895652",
    "content": {
      "latitude": 33.983333,
      "longitude": 35.633333,
      "name": "Jounieh, Lebanon"
    }
  }'
```

## 🎉 Verified Working Example
**✅ Jounieh Location Successfully Sent!**
- **Coordinates**: 33.983333, 35.633333
- **Message ID**: `1e5671ed-062d-49cf-81b5-3fdb7d73ed5e`
- **Recipient**: antonio (96170895652)
- **Status**: ✅ PENDING_ENROUTE

## 💡 Pro Tips
- Use 4-6 decimal places for accuracy
- Test coordinates on Google Maps first
- Include name/address for better UX
- Validate ranges before sending 