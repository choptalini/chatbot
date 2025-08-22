#!/usr/bin/env python3
"""
Test script for Shopify webhook endpoint.
Simulates webhook requests to verify HMAC signature validation and processing.
"""

import os
import sys
import json
import hmac
import hashlib
import base64
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Test webhook secret (should match SHOPIFY_WEBHOOK_SECRET in your .env)
WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET", "test-secret").encode("utf-8")
WEBHOOK_URL = "http://localhost:8000/webhook/shopify"

def create_hmac_signature(payload: str, secret: bytes) -> str:
    """Create HMAC signature for webhook payload."""
    digest = hmac.new(secret, payload.encode('utf-8'), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()

def test_product_create():
    """Test product creation webhook."""
    payload = {
        "id": 12345,
        "title": "Test Product",
        "body_html": "<p>This is a test product created for webhook testing.</p>",
        "vendor": "Test Vendor",
        "product_type": "Test Category",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "published_at": datetime.now().isoformat(),
        "handle": "test-product",
        "status": "active",
        "variants": [
            {
                "id": 67890,
                "product_id": 12345,
                "title": "Default Title",
                "price": "29.99",
                "sku": "TEST-001",
                "inventory_quantity": 100
            }
        ],
        "options": [
            {
                "id": 1111,
                "product_id": 12345,
                "name": "Title",
                "position": 1,
                "values": ["Default Title"]
            }
        ],
        "images": []
    }
    
    return send_webhook_request("products/create", payload)

def test_product_update():
    """Test product update webhook."""
    payload = {
        "id": 12345,
        "title": "Updated Test Product",
        "body_html": "<p>This product has been updated via webhook.</p>",
        "vendor": "Updated Vendor",
        "product_type": "Updated Category",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": datetime.now().isoformat(),
        "published_at": "2024-01-01T00:00:00Z",
        "handle": "updated-test-product",
        "status": "active",
        "variants": [
            {
                "id": 67890,
                "product_id": 12345,
                "title": "Default Title",
                "price": "39.99",  # Updated price
                "sku": "TEST-001-UPDATED",
                "inventory_quantity": 150
            }
        ]
    }
    
    return send_webhook_request("products/update", payload)

def test_product_delete():
    """Test product deletion webhook."""
    payload = {
        "id": 12345,
        "title": "Deleted Test Product",
        "deleted_at": datetime.now().isoformat()
    }
    
    return send_webhook_request("products/delete", payload)

def test_invalid_signature():
    """Test webhook with invalid HMAC signature."""
    payload = {"id": 99999, "title": "Invalid Signature Test"}
    payload_str = json.dumps(payload)
    
    # Create an intentionally wrong signature
    wrong_signature = "invalid-signature"
    
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Topic": "products/create",
        "X-Shopify-Hmac-Sha256": wrong_signature,
        "X-Shopify-Shop-Domain": "test-shop.myshopify.com"
    }
    
    try:
        response = requests.post(WEBHOOK_URL, data=payload_str, headers=headers, timeout=10)
        print(f"❌ Invalid signature test - Status: {response.status_code}")
        if response.status_code != 401:
            print(f"   Expected 401, got {response.status_code}")
            return False
        else:
            print(f"   ✅ Correctly rejected invalid signature")
            return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def send_webhook_request(topic: str, payload: dict) -> bool:
    """Send a webhook request with proper HMAC signature."""
    payload_str = json.dumps(payload)
    signature = create_hmac_signature(payload_str, WEBHOOK_SECRET)
    
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Topic": topic,
        "X-Shopify-Hmac-Sha256": signature,
        "X-Shopify-Shop-Domain": "test-shop.myshopify.com"
    }
    
    try:
        response = requests.post(WEBHOOK_URL, data=payload_str, headers=headers, timeout=10)
        print(f"📦 {topic} - Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ Success: {response.json()}")
            return True
        else:
            print(f"   ❌ Failed: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def test_missing_headers():
    """Test webhook with missing required headers."""
    payload = {"id": 88888, "title": "Missing Headers Test"}
    payload_str = json.dumps(payload)
    
    # Missing X-Shopify-Topic and X-Shopify-Hmac-Sha256
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(WEBHOOK_URL, data=payload_str, headers=headers, timeout=10)
        print(f"🚫 Missing headers test - Status: {response.status_code}")
        if response.status_code != 400:
            print(f"   Expected 400, got {response.status_code}")
            return False
        else:
            print(f"   ✅ Correctly rejected missing headers")
            return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def main():
    """Run all webhook tests."""
    print("🧪 Testing Shopify Webhook Endpoint")
    print("=" * 50)
    print(f"Target URL: {WEBHOOK_URL}")
    print(f"Using secret: {'*' * (len(str(WEBHOOK_SECRET)) - 4)}{str(WEBHOOK_SECRET)[-4:]}")
    print()
    
    tests = [
        ("Product Create", test_product_create),
        ("Product Update", test_product_update),
        ("Product Delete", test_product_delete),
        ("Invalid Signature", test_invalid_signature),
        ("Missing Headers", test_missing_headers),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"Running {test_name} test...")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))
        print()
    
    # Summary
    print("📊 Test Results:")
    print("-" * 30)
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! Webhook endpoint is working correctly.")
        sys.exit(0)
    else:
        print("⚠️ Some tests failed. Check the webhook implementation.")
        sys.exit(1)

if __name__ == "__main__":
    main()