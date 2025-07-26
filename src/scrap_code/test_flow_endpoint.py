#!/usr/bin/env python3
"""
WhatsApp Flow Endpoint Test Script

This script tests the encryption/decryption functionality of the Flow endpoint.
"""

import json
import base64
import requests
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.padding import OAEP, MGF1, hashes
from cryptography.hazmat.primitives.ciphers import algorithms, Cipher, modes
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from dotenv import load_dotenv
import os

# Load environment
load_dotenv('.env.flow')

def load_public_key():
    """Load the public key from the keys directory."""
    try:
        with open('keys/public_key.pem', 'r') as f:
            public_key_pem = f.read()
        return load_pem_public_key(public_key_pem.encode('utf-8'))
    except FileNotFoundError:
        print("❌ Public key file not found. Please run the key generator first.")
        return None

def create_test_request():
    """Create a test encrypted request similar to what WhatsApp would send."""
    
    # Load public key
    public_key = load_public_key()
    if not public_key:
        return None
    
    # Create test data
    test_data = {
        "version": "3.0",
        "action": "ping"
    }
    
    # Generate AES key
    aes_key = os.urandom(16)  # 128-bit key
    iv = os.urandom(16)  # 128-bit IV
    
    # Encrypt data with AES-GCM
    encryptor = Cipher(algorithms.AES(aes_key), modes.GCM(iv)).encryptor()
    encrypted_data = encryptor.update(json.dumps(test_data).encode('utf-8')) + encryptor.finalize()
    encrypted_data_with_tag = encrypted_data + encryptor.tag
    
    # Encrypt AES key with RSA
    encrypted_aes_key = public_key.encrypt(
        aes_key,
        OAEP(
            mgf=MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    # Prepare request payload
    request_payload = {
        "encrypted_flow_data": base64.b64encode(encrypted_data_with_tag).decode('utf-8'),
        "encrypted_aes_key": base64.b64encode(encrypted_aes_key).decode('utf-8'),
        "initial_vector": base64.b64encode(iv).decode('utf-8')
    }
    
    return request_payload

def test_health_endpoint():
    """Test the health endpoint."""
    try:
        response = requests.get("http://localhost:8080/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health endpoint working")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is it running?")
    except Exception as e:
        print(f"❌ Health test failed: {e}")

def test_flow_endpoint():
    """Test the encrypted Flow endpoint."""
    # Create test request
    test_request = create_test_request()
    if not test_request:
        print("❌ Failed to create test request")
        return
    
    try:
        # Send request to Flow endpoint
        response = requests.post(
            "http://localhost:8080/ecla_flow",
            json=test_request,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Flow endpoint working")
            print(f"Response (encrypted): {response.text[:100]}...")
        else:
            print(f"❌ Flow endpoint failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is it running?")
    except Exception as e:
        print(f"❌ Flow test failed: {e}")

def test_ngrok_endpoint():
    """Test the ngrok public endpoint."""
    ngrok_url = "https://first-logical-tadpole.ngrok-free.app"
    
    # Test health first
    try:
        response = requests.get(f"{ngrok_url}/health", timeout=10)
        if response.status_code == 200:
            print("✅ Ngrok health endpoint working")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Ngrok health endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Ngrok health test failed: {e}")
    
    # Test Flow endpoint
    test_request = create_test_request()
    if not test_request:
        return
    
    try:
        response = requests.post(
            f"{ngrok_url}/ecla_flow",
            json=test_request,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Ngrok Flow endpoint working")
            print(f"Response (encrypted): {response.text[:100]}...")
        else:
            print(f"❌ Ngrok Flow endpoint failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Ngrok Flow test failed: {e}")

def main():
    """Run all tests."""
    print("🧪 Testing WhatsApp Flow Endpoint")
    print("=" * 50)
    
    print("\n1. Testing Local Health Endpoint:")
    test_health_endpoint()
    
    print("\n2. Testing Local Flow Endpoint:")
    test_flow_endpoint()
    
    print("\n3. Testing Ngrok Endpoints:")
    test_ngrok_endpoint()
    
    print("\n" + "=" * 50)
    print("✅ Testing complete!")
    
    print("\n📋 Next Steps:")
    print("1. Upload the public key to WhatsApp Business API")
    print("2. Configure your Flow to use: https://first-logical-tadpole.ngrok-free.app/ecla_flow")
    print("3. Set data_api_version to '3.0' in your Flow JSON")
    print("4. Test with a real WhatsApp Flow")

if __name__ == "__main__":
    main() 