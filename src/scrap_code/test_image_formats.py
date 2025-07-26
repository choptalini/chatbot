#!/usr/bin/env python3
"""
Simple Image Format Tester for WhatsApp
Tests different image formats with Infobip API
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_image_format(image_url, format_name, recipient="96170895652"):
    """Test sending an image of a specific format"""
    
    api_key = os.getenv("INFOBIP_API_KEY")
    base_url = os.getenv("INFOBIP_BASE_URL")
    sender = os.getenv("WHATSAPP_SENDER")
    
    if not base_url.startswith('http'):
        base_url = f"https://{base_url}"
    
    payload = {
        "from": sender,
        "to": recipient,
        "content": {
            "mediaUrl": image_url,
            "caption": f"🧪 Testing {format_name} format"
        }
    }
    
    headers = {
        "Authorization": f"App {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(f"{base_url}/whatsapp/1/message/image", 
                               json=payload, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            message_id = result.get('messageId', 'N/A')
            print(f"✅ {format_name}: SUCCESS | Message ID: {message_id}")
            return True
        else:
            print(f"❌ {format_name}: FAILED | Status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ {format_name}: ERROR | {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Image Formats with Infobip WhatsApp API")
    print("=" * 60)
    
    # Test different formats
    formats = [
        ("JPEG", "https://picsum.photos/500/300.jpg"),
        ("PNG", "https://via.placeholder.com/400x200.png"),
        ("WebP (Bionic)", "https://cdn.shopify.com/s/files/1/0715/1668/4484/files/bionic2_1600x_05ad8cb7-411e-4c1f-8b95-f18c38a331c3.webp?v=1752181116")
    ]
    
    for format_name, url in formats:
        test_image_format(url, format_name)
    
    print("=" * 60)
    print("💡 Check antonio's WhatsApp for the test images!") 