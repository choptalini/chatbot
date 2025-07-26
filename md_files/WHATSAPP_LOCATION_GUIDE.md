# 📍 WhatsApp Location Messages with Infobip API

## ✅ Success! Location Sent

**Message ID**: `1e5671ed-062d-49cf-81b5-3fdb7d73ed5e`  
**Status**: PENDING_ENROUTE  
**Recipient**: antonio (96170895652)  
**Location**: Jounieh, Lebanon (33.983333, 35.633333)

## 📍 Overview

The Infobip WhatsApp Business API supports sending location messages that display as interactive maps in WhatsApp. Recipients can tap to open the location in their preferred map application (Google Maps, Apple Maps, etc.).

## 📋 Prerequisites

- ✅ **Infobip Account** with WhatsApp Business API access
- ✅ **API Key** and Base URL from Infobip
- ✅ **WhatsApp Business Number** (sender)
- ✅ **24-hour messaging window** or approved template

## 🔧 API Endpoint

### Location Message Endpoint
```
POST https://{base_url}/whatsapp/1/message/location
```

### Headers Required
```http
Authorization: App {your_api_key}
Content-Type: application/json
Accept: application/json
```

## 📦 Request Payload Structure

### Basic Location Message
```json
{
  "from": "96179374241",
  "to": "96170895652",
  "content": {
    "latitude": 33.983333,
    "longitude": 35.633333
  }
}
```

### Location Message with Name and Address
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

## 🎯 Implementation Examples

### Python Example (Using Requests)
```python
import requests

def send_whatsapp_location(api_key, base_url, sender, recipient, latitude, longitude, name="", address=""):
    endpoint = f"https://{base_url}/whatsapp/1/message/location"
    
    headers = {
        "Authorization": f"App {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "from": sender,
        "to": recipient,
        "content": {
            "latitude": latitude,
            "longitude": longitude
        }
    }
    
    if name:
        payload["content"]["name"] = name
    if address:
        payload["content"]["address"] = address
    
    response = requests.post(endpoint, json=payload, headers=headers)
    return response.json()

# Usage - Send Jounieh, Lebanon location
result = send_whatsapp_location(
    api_key="your_api_key",
    base_url="your_base_url",
    sender="96179374241",
    recipient="96170895652",
    latitude=33.983333,
    longitude=35.633333,
    name="Jounieh, Lebanon",
    address="Jounieh, Mount Lebanon Governorate, Lebanon"
)
```

### JavaScript/Node.js Example
```javascript
const axios = require('axios');

async function sendWhatsAppLocation(apiKey, baseUrl, sender, recipient, latitude, longitude, name = '', address = '') {
    const endpoint = `https://${baseUrl}/whatsapp/1/message/location`;
    
    const headers = {
        'Authorization': `App ${apiKey}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    };
    
    const payload = {
        from: sender,
        to: recipient,
        content: {
            latitude: latitude,
            longitude: longitude
        }
    };
    
    if (name) payload.content.name = name;
    if (address) payload.content.address = address;
    
    try {
        const response = await axios.post(endpoint, payload, { headers });
        return response.data;
    } catch (error) {
        console.error('Error sending location:', error.response?.data || error.message);
        throw error;
    }
}

// Usage
sendWhatsAppLocation(
    'your_api_key',
    'your_base_url',
    '96179374241',
    '96170895652',
    33.983333,
    35.633333,
    'Jounieh, Lebanon',
    'Jounieh, Mount Lebanon Governorate, Lebanon'
);
```

### cURL Example
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
      "name": "Jounieh, Lebanon",
      "address": "Jounieh, Mount Lebanon Governorate, Lebanon"
    }
  }'
```

## 📊 Response Format

### Successful Response (200 OK)
```json
{
  "to": "96170895652",
  "messageCount": 1,
  "messageId": "1e5671ed-062d-49cf-81b5-3fdb7d73ed5e",
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
          "field": "content.latitude",
          "message": "Invalid latitude value"
        }
      ]
    }
  }
}
```

## 🌍 Coordinate Requirements

### Technical Specifications
- **Latitude range**: -90 to +90 degrees
- **Longitude range**: -180 to +180 degrees
- **Precision**: Up to 6 decimal places recommended
- **Format**: Decimal degrees (not DMS)

### Field Requirements
| Field | Type | Required | Max Length | Description |
|-------|------|----------|------------|-------------|
| latitude | number | ✅ Yes | - | Latitude in decimal degrees |
| longitude | number | ✅ Yes | - | Longitude in decimal degrees |
| name | string | ❌ No | 1000 chars | Location name/title |
| address | string | ❌ No | 1000 chars | Full address description |

## 🗺️ Popular Lebanon Coordinates

### Major Cities
```javascript
const lebanonLocations = {
  beirut: { lat: 33.888630, lon: 35.495480, name: "Beirut, Lebanon" },
  jounieh: { lat: 33.983333, lon: 35.633333, name: "Jounieh, Lebanon" },
  tripoli: { lat: 34.436667, lon: 35.833333, name: "Tripoli, Lebanon" },
  baalbek: { lat: 34.006667, lon: 36.204167, name: "Baalbek, Lebanon" },
  tyre: { lat: 33.271992, lon: 35.203487, name: "Tyre, Lebanon" },
  sidon: { lat: 33.557144, lon: 35.369115, name: "Sidon, Lebanon" },
  zahle: { lat: 33.846667, lon: 35.901111, name: "Zahle, Lebanon" }
};
```

## 🎨 Best Practices

### Coordinate Accuracy
1. **Use precise coordinates** - At least 4-6 decimal places for accuracy
2. **Validate coordinates** - Ensure they're within valid ranges
3. **Test locations** - Verify coordinates point to correct locations
4. **Consider timezone** - Location context for time-sensitive messages

### Naming Guidelines
- **Be descriptive**: Include city/region for clarity
- **Use local language**: Consider recipient's language preference  
- **Add context**: Business name, landmark, or area description
- **Keep concise**: Avoid overly long names

### Error Handling
```python
def send_location_with_validation(latitude, longitude, name="", address=""):
    # Validate coordinates
    if not (-90 <= latitude <= 90):
        raise ValueError("Latitude must be between -90 and 90")
    if not (-180 <= longitude <= 180):
        raise ValueError("Longitude must be between -180 and 180")
    
    # Validate string lengths
    if len(name) > 1000:
        raise ValueError("Name must be 1000 characters or less")
    if len(address) > 1000:
        raise ValueError("Address must be 1000 characters or less")
    
    return send_whatsapp_location(latitude, longitude, name, address)
```

## 🔍 Common Issues & Solutions

### 1. Invalid Coordinates
**Problem**: Coordinates outside valid ranges
```
❌ Error: "Invalid latitude/longitude value"
```

**Solutions**:
- ✅ Latitude: -90 to +90 degrees
- ✅ Longitude: -180 to +180 degrees  
- ✅ Use decimal format (33.983333, not 33°58'N)
- ✅ Validate ranges before sending

### 2. Location Not Found
**Problem**: Location appears in wrong place or ocean
```
🌊 Location shows in ocean instead of land
```

**Solutions**:
- ✅ Double-check coordinate order (latitude first, longitude second)
- ✅ Verify coordinates using maps.google.com
- ✅ Use coordinate validation tools
- ✅ Test with known coordinates first

### 3. Missing Location Details
**Problem**: Location shows coordinates but no name/address
```
📍 Shows "33.983333, 35.633333" instead of "Jounieh, Lebanon"
```

**Solutions**:
- ✅ Include `name` field for location title
- ✅ Include `address` field for full address
- ✅ Use descriptive, recognizable names
- ✅ Test without optional fields first

## 🚀 Advanced Features

### 1. Coordinate Validation
```python
import requests

def validate_coordinates(latitude, longitude):
    """Validate coordinates using reverse geocoding"""
    try:
        # Simple validation
        if not (-90 <= latitude <= 90):
            return False, "Invalid latitude range"
        if not (-180 <= longitude <= 180):
            return False, "Invalid longitude range"
        
        # Optional: Use reverse geocoding API to verify location exists
        # This is just an example - you'd use your preferred geocoding service
        url = f"https://api.example.com/reverse?lat={latitude}&lon={longitude}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            return True, "Valid coordinates"
        else:
            return False, "Coordinates not found"
            
    except Exception as e:
        return False, f"Validation error: {e}"

# Usage
is_valid, message = validate_coordinates(33.983333, 35.633333)
if is_valid:
    send_whatsapp_location(...)
else:
    print(f"Invalid coordinates: {message}")
```

### 2. Batch Location Sending
```python
def send_multiple_locations(recipients, locations):
    """Send same location to multiple recipients"""
    results = []
    
    for recipient in recipients:
        for location in locations:
            try:
                result = send_whatsapp_location(
                    api_key=API_KEY,
                    base_url=BASE_URL,
                    sender=SENDER,
                    recipient=recipient,
                    latitude=location['lat'],
                    longitude=location['lon'],
                    name=location.get('name', ''),
                    address=location.get('address', '')
                )
                results.append({
                    'recipient': recipient,
                    'location': location['name'],
                    'success': True,
                    'message_id': result.get('messageId'),
                    'result': result
                })
            except Exception as e:
                results.append({
                    'recipient': recipient,
                    'location': location['name'],
                    'success': False,
                    'error': str(e)
                })
    
    return results
```

### 3. Location Library System
```python
class LocationLibrary:
    def __init__(self):
        self.locations = {
            'lebanon': {
                'beirut': {'lat': 33.888630, 'lon': 35.495480, 'name': 'Beirut, Lebanon'},
                'jounieh': {'lat': 33.983333, 'lon': 35.633333, 'name': 'Jounieh, Lebanon'},
                'baalbek': {'lat': 34.006667, 'lon': 36.204167, 'name': 'Baalbek, Lebanon'},
            },
            'uae': {
                'dubai': {'lat': 25.276987, 'lon': 55.296249, 'name': 'Dubai, UAE'},
                'abu_dhabi': {'lat': 24.453884, 'lon': 54.377344, 'name': 'Abu Dhabi, UAE'},
            }
        }
    
    def get_location(self, country, city):
        return self.locations.get(country, {}).get(city)
    
    def send_saved_location(self, recipient, country, city):
        location = self.get_location(country, city)
        if location:
            return send_whatsapp_location(
                recipient=recipient,
                latitude=location['lat'],
                longitude=location['lon'],
                name=location['name']
            )
        else:
            raise ValueError(f"Location not found: {country}/{city}")

# Usage
library = LocationLibrary()
library.send_saved_location("96170895652", "lebanon", "jounieh")
```

## 🔗 Related Message Types

### Text Message with Location Context
```python
# Send location followed by text message
location_result = send_whatsapp_location(lat, lon, name, address)
if location_result.get('messageId'):
    text_result = send_text_message(
        recipient, 
        "📍 This is our office location. See you there!"
    )
```

### Template Message with Location
```python
# Use location in template message variables
template_result = send_template_message(
    recipient=recipient,
    template_name="meeting_location",
    variables=[name, address, "2:00 PM"]
)
```

## 🎯 Quick Reference

### Location Message Checklist
- [ ] Latitude is between -90 and +90
- [ ] Longitude is between -180 and +180  
- [ ] Coordinates are in decimal format
- [ ] Name is under 1000 characters (if provided)
- [ ] Address is under 1000 characters (if provided)
- [ ] Within 24-hour messaging window or using approved template
- [ ] API credentials are correct
- [ ] Error handling is implemented

### Status Codes
| Code | Status | Description |
|------|--------|-------------|
| 200 | Success | Location sent successfully |
| 400 | Bad Request | Invalid coordinates or parameters |
| 401 | Unauthorized | Invalid API key |
| 403 | Forbidden | Access denied or rate limited |
| 404 | Not Found | Endpoint not found |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Server Error | Infobip server error |

## 🎉 Example Success: Beirut Jounieh Location

**✅ Successfully sent Jounieh location to antonio!**

- **Coordinates**: 33.983333, 35.633333
- **Location**: Jounieh, Lebanon
- **Message ID**: `1e5671ed-062d-49cf-81b5-3fdb7d73ed5e`
- **Recipient**: antonio (96170895652)
- **Address**: "Jounieh, Mount Lebanon Governorate, Lebanon"
- **Status**: PENDING_ENROUTE (Successfully queued for delivery)

The location should appear as an interactive map in antonio's WhatsApp that he can tap to open in his map app! 📱🗺️ 