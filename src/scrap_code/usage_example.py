#!/usr/bin/env python3
"""
Usage Example for the infobip-whatsapp-methods SDK

This file demonstrates how to use the WhatsAppClient for common operations
like sending text messages and images.
"""

import os
from dotenv import load_dotenv
from infobip_whatsapp_methods import WhatsAppClient

# Load environment variables from .env file
load_dotenv()

def main():
    """Main function to demonstrate SDK usage."""
    print(" infobip-whatsapp-methods SDK Usage Example")
    print("=" * 50)
    
    try:
        # Initialize the client from environment variables
        client = WhatsAppClient()
        
        # --- 1. Get Client Info ---
        print("\n1. Client Information:")
        client_info = client.get_client_info()
        for key, value in client_info.items():
            print(f"  - {key.replace('_', ' ').title()}: {value}")
            
        # --- 2. Send a Test Text Message ---
        # The target number should be in international format (e.g., 96170895652)
        target_number = "96170895652"
        print(f"\n2. Sending a test text message to: {target_number}...")
        
        text_message = f"Hello from the new infobip-whatsapp-methods SDK! This is a test message. "
        
        text_response = client.send_text_message(target_number, text_message)
        
        if text_response.success:
            print(f"  Success! Message ID: {text_response.message_id}")
        else:
            print(f"  Failed to send text message: {text_response.error}")
            
        # --- 3. Send a Test Image Message ---
        print(f"\n3. Sending a test image to: {target_number}...")
        
        # Using a direct Shopify CDN link which is more likely to be accessible by WhatsApp servers.
        image_url = "https://cdn.shopify.com/s/files/1/0715/1668/4484/files/bionic2_1600x_05ad8cb7-411e-4c1f-8b95-f18c38a331c3.webp?v=1752181116"
        image_caption = "This is a test image from a Shopify CDN, sent from the new SDK!"
        
        image_response = client.send_image(target_number, image_url, image_caption)
        
        if image_response.success:
            print(f"  Success! Message ID: {image_response.message_id}")
        else:
            print(f"  Failed to send image: {image_response.error}")
            
        # --- 4. Send a Preset Location Message ---
        print(f"\n4. Sending a preset location to: {target_number}...")
        
        location_response = client.send_location_preset(target_number, "jounieh")
        
        if location_response.success:
            print(f"  Success! Message ID: {location_response.message_id}")
        else:
            print(f"  Failed to send location: {location_response.error}")
        
    except Exception as e:
        print(f"\n An error occurred: {e}")
        print(" Please ensure your .env file is correctly configured with:")
        print(" - INFOBIP_API_KEY")
        print(" - INFOBIP_BASE_URL")
        print(" - WHATSAPP_SENDER")

if __name__ == "__main__":
    main() 