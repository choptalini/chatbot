#!/usr/bin/env python3
"""
Test script for WhatsApp webhook functionality
"""

import requests
import json
from datetime import datetime

def test_webhook():
    """Test the webhook endpoint"""
    webhook_url = "http://localhost:8000/webhook"
    
    # Sample message payload
    test_payload = {
        "results": [{
            "messageId": f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "from": "96170895652",
            "to": "96179374241",
            "message": {
                "type": "text",
                "text": "Hello! This is a test message from the webhook test script."
            },
            "contact": {
                "name": "Antonio Test"
            }
        }]
    }
    
    print("🧪 Testing webhook endpoint...")
    print(f"📡 URL: {webhook_url}")
    print(f"📦 Payload: {json.dumps(test_payload, indent=2)}")
    
    try:
        response = requests.post(webhook_url, json=test_payload)
        
        if response.status_code == 200:
            print("✅ Webhook test successful!")
            print(f"📋 Response: {response.json()}")
            
            # Check if message was stored
            messages_response = requests.get("http://localhost:8000/messages")
            if messages_response.status_code == 200:
                messages = messages_response.json()
                print(f"📱 Total messages stored: {messages['count']}")
                
                # Show latest message
                if messages['messages']:
                    latest = messages['messages'][0]
                    print(f"📄 Latest message: {latest}")
                    
            return True
        else:
            print(f"❌ Webhook test failed: {response.status_code}")
            print(f"📄 Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing webhook: {e}")
        return False

def get_server_status():
    """Check server status"""
    try:
        response = requests.get("http://localhost:8000/health")
        if response.status_code == 200:
            health = response.json()
            print("🏥 Server Health:")
            print(f"  Status: {health['status']}")
            print(f"  Timestamp: {health['timestamp']}")
            print(f"  API Key: {'✅ Configured' if health.get('api_key_configured') else '❌ Missing'}")
            return True
        else:
            print(f"❌ Server health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return False

def main():
    """Main test function"""
    print("WhatsApp Webhook Test")
    print("=" * 50)
    
    # Check server status
    if not get_server_status():
        print("❌ Server not running. Please start with: python whatsapp_message_fetcher.py")
        return
    
    print()
    
    # Test webhook
    if test_webhook():
        print("\n🎉 All tests passed! Your webhook is ready.")
        print("\n📝 Next steps:")
        print("1. Set up public URL (ngrok/cloudflare)")
        print("2. Configure Infobip webhook URL")
        print("3. Send test messages to your WhatsApp number")
    else:
        print("\n❌ Tests failed. Please check the server logs.")

if __name__ == "__main__":
    main() 