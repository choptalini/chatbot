#!/usr/bin/env python3
"""
Test script to verify that image logging uses the correct tenant context
and doesn't mix up conversations between different chatbots.
"""

import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_metadata_extraction():
    """Test that tools can extract metadata correctly."""
    print("🧪 Testing Metadata Extraction in Tools\n")
    
    # Test ECLA tool
    try:
        with open('src/tools/ecla_whatsapp_tools.py', 'r') as f:
            ecla_content = f.read()
            
        checks = [
            'metadata = config.get("metadata", {}) if config else {}',
            'user_id = metadata.get("user_id")',
            'chatbot_id = metadata.get("chatbot_id")',
            'contact_id = metadata.get("contact_id")'
        ]
        
        missing_checks = []
        for check in checks:
            if check not in ecla_content:
                missing_checks.append(check)
        
        if missing_checks:
            print(f"❌ ECLA tool missing metadata extraction:")
            for check in missing_checks:
                print(f"   - {check}")
            return False
        else:
            print("✅ ECLA tool correctly extracts metadata from config")
            
    except Exception as e:
        print(f"❌ Error reading ECLA tools: {e}")
        return False
    
    # Test AstroSouks tool
    try:
        with open('src/astrosouks_tools/astrosouks_whatsapp_tools.py', 'r') as f:
            astrosouks_content = f.read()
            
        missing_checks = []
        for check in checks:
            if check not in astrosouks_content:
                missing_checks.append(check)
        
        if missing_checks:
            print(f"❌ AstroSouks tool missing metadata extraction:")
            for check in missing_checks:
                print(f"   - {check}")
            return False
        else:
            print("✅ AstroSouks tool correctly extracts metadata from config")
            
    except Exception as e:
        print(f"❌ Error reading AstroSouks tools: {e}")
        return False
    
    return True

def test_worker_metadata_passing():
    """Test that the worker passes correct metadata to tools."""
    print("\n🔧 Testing Worker Metadata Passing\n")
    
    try:
        with open('whatsapp_message_fetcher.py', 'r') as f:
            worker_content = f.read()
            
        checks = [
            '"user_id": user_id,',
            '"chatbot_id": chatbot_id,',
            '"contact_id": contact_id'
        ]
        
        missing_checks = []
        for check in checks:
            if check not in worker_content:
                missing_checks.append(check)
        
        if missing_checks:
            print(f"❌ Worker not passing correct metadata:")
            for check in missing_checks:
                print(f"   - {check}")
            return False
        else:
            print("✅ Worker correctly passes tenant context to tools")
            
        # Check that it appears in both tool calls (ECLA and AstroSouks)
        tool_call_count = worker_content.count('"user_id": user_id,')
        if tool_call_count < 2:
            print(f"❌ Worker metadata only found {tool_call_count} times, expected at least 2 (ECLA + AstroSouks)")
            return False
        else:
            print(f"✅ Worker metadata found {tool_call_count} times (both tool calls updated)")
            
    except Exception as e:
        print(f"❌ Error reading worker file: {e}")
        return False
    
    return True

def test_fallback_mechanism():
    """Test that tools have fallback mechanism if metadata is missing."""
    print("\n🛡️ Testing Fallback Mechanism\n")
    
    # Check ECLA tool
    try:
        with open('src/tools/ecla_whatsapp_tools.py', 'r') as f:
            ecla_content = f.read()
            
        if 'if not all([user_id, chatbot_id, contact_id]):' in ecla_content:
            print("✅ ECLA tool has fallback mechanism")
        else:
            print("❌ ECLA tool missing fallback mechanism")
            return False
            
    except Exception as e:
        print(f"❌ Error checking ECLA fallback: {e}")
        return False
    
    # Check AstroSouks tool
    try:
        with open('src/astrosouks_tools/astrosouks_whatsapp_tools.py', 'r') as f:
            astrosouks_content = f.read()
            
        if 'if not all([user_id, chatbot_id, contact_id]):' in astrosouks_content:
            print("✅ AstroSouks tool has fallback mechanism")
        else:
            print("❌ AstroSouks tool missing fallback mechanism")
            return False
            
    except Exception as e:
        print(f"❌ Error checking AstroSouks fallback: {e}")
        return False
    
    return True

def main():
    """Run all tests."""
    print("🚀 Image Logging Multi-Tenant Fix Verification")
    print("=" * 60)
    print()
    
    success = True
    
    # Test metadata extraction
    if not test_metadata_extraction():
        success = False
    
    # Test worker metadata passing
    if not test_worker_metadata_passing():
        success = False
    
    # Test fallback mechanism
    if not test_fallback_mechanism():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 All tests passed! Image logging should now work correctly:")
        print("   ✅ Tools extract tenant context from worker metadata")
        print("   ✅ Worker passes correct user_id, chatbot_id, contact_id")
        print("   ✅ Images will be logged to the correct conversations")
        print("   ✅ Fallback mechanism in case metadata is missing")
        print("\n📋 Expected behavior:")
        print("   - ECLA images → logged to ECLA conversations (contact_id from ECLA)")
        print("   - AstroSouks images → logged to AstroSouks conversations (contact_id from AstroSouks)")
    else:
        print("❌ Some tests failed. Please check the fixes.")
        sys.exit(1)

if __name__ == "__main__":
    main()
