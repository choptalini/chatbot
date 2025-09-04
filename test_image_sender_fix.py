#!/usr/bin/env python3
"""
Test script to verify that image sending uses the correct WhatsApp sender
based on the agent/chatbot being used.
"""

import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config.settings import settings

def test_sender_configuration():
    """Test that the environment variables are correctly loaded."""
    print("🧪 Testing WhatsApp Sender Configuration\n")
    
    # Load environment variables
    load_dotenv()
    
    print("📋 Current sender configuration:")
    print(f"ECLA (SwiftReplies) sender: {settings.whatsapp_sender}")
    print(f"AstroSouks sender: {settings.astrosouks_whatsapp_sender}")
    print()
    
    # Verify both are configured
    if not settings.whatsapp_sender:
        print("❌ ECLA WhatsApp sender not configured!")
        return False
        
    if not settings.astrosouks_whatsapp_sender:
        print("❌ AstroSouks WhatsApp sender not configured!")
        return False
        
    if settings.whatsapp_sender == settings.astrosouks_whatsapp_sender:
        print("❌ Both senders are the same! They should be different.")
        return False
        
    print("✅ Both senders are properly configured and different")
    return True

def test_tools_configuration():
    """Test that the tools use the correct senders."""
    print("🔧 Testing Tools Configuration\n")
    
    # Test AstroSouks tool
    try:
        # Read the AstroSouks tools file
        with open('src/astrosouks_tools/astrosouks_whatsapp_tools.py', 'r') as f:
            astrosouks_content = f.read()
            
        if 'settings.astrosouks_whatsapp_sender' in astrosouks_content:
            print("✅ AstroSouks tool uses correct sender (astrosouks_whatsapp_sender)")
        else:
            print("❌ AstroSouks tool NOT using correct sender!")
            return False
            
    except Exception as e:
        print(f"❌ Error reading AstroSouks tools: {e}")
        return False
    
    # Test ECLA tool
    try:
        # Read the ECLA tools file
        with open('src/tools/ecla_whatsapp_tools.py', 'r') as f:
            ecla_content = f.read()
            
        if 'settings.whatsapp_sender' in ecla_content:
            print("✅ ECLA tool uses correct sender (whatsapp_sender)")
        else:
            print("❌ ECLA tool NOT using correct sender!")
            return False
            
    except Exception as e:
        print(f"❌ Error reading ECLA tools: {e}")
        return False
    
    return True

def main():
    """Run all tests."""
    print("🚀 WhatsApp Image Sender Fix Verification")
    print("=" * 50)
    print()
    
    success = True
    
    # Test sender configuration
    if not test_sender_configuration():
        success = False
    
    # Test tools configuration
    if not test_tools_configuration():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed! Image sending should now work correctly:")
        print("   - ECLA messages will send images from:", settings.whatsapp_sender)
        print("   - AstroSouks messages will send images from:", settings.astrosouks_whatsapp_sender)
    else:
        print("❌ Some tests failed. Please check the configuration.")
        sys.exit(1)

if __name__ == "__main__":
    main()
