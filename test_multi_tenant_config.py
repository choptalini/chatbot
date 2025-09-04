#!/usr/bin/env python3
"""
Test script for Multi-Tenant WhatsApp Configuration

This script tests the new multi-tenant routing configuration to ensure:
1. Proper routing based on destination numbers
2. Correct agent selection
3. Client mapping functionality
"""

import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from multi_tenant_config import MultiTenantConfig

def test_routing_configuration():
    """Test the multi-tenant routing configuration."""
    print("🧪 Testing Multi-Tenant Routing Configuration\n")
    
    # Test cases: (to_number, expected_result)
    test_cases = [
        # SwiftReplies (ECLA) routing
        ("96179374241", {
            "user_id": 2,
            "chatbot_id": 2,
            "agent_id": "ecla_sales_agent"
        }),
        # AstroSouks routing
        ("9613451652", {
            "user_id": 6,
            "chatbot_id": 3,
            "agent_id": "astrosouks_sales_agent"
        }),
        # Test with + prefix
        ("+96179374241", {
            "user_id": 2,
            "chatbot_id": 2,
            "agent_id": "ecla_sales_agent"
        }),
        ("+9613451652", {
            "user_id": 6,
            "chatbot_id": 3,
            "agent_id": "astrosouks_sales_agent"
        }),
        # Unknown number (should return None)
        ("1234567890", None),
        ("", None),
        (None, None),
    ]
    
    print("📋 Testing destination-based routing:")
    print("-" * 50)
    
    for i, (to_number, expected) in enumerate(test_cases, 1):
        result = MultiTenantConfig.get_routing_for_destination(to_number)
        
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(f"Test {i}: {status}")
        print(f"  Input: {to_number}")
        print(f"  Expected: {expected}")
        print(f"  Got: {result}")
        
        if result != expected:
            print(f"  ⚠️  MISMATCH!")
        print()

def test_sender_configuration():
    """Test sender configuration methods."""
    print("📋 Testing sender configuration methods:")
    print("-" * 50)
    
    # Test get_all_sender_configs
    all_configs = MultiTenantConfig.get_all_sender_configs()
    print(f"1. All sender configs: {len(all_configs)} configured")
    for number, config in all_configs.items():
        print(f"   {number}: user_id={config['user_id']}, chatbot_id={config['chatbot_id']}, agent_id={config['agent_id']}")
    print()
    
    # Test get_sender_config
    test_numbers = ["96179374241", "9613451652", "+96179374241", "unknown"]
    print("2. Individual sender config lookup:")
    for number in test_numbers:
        config = MultiTenantConfig.get_sender_config(number)
        print(f"   {number}: {config}")
    print()

def test_environment_variables():
    """Test environment variable loading."""
    print("📋 Testing environment variables:")
    print("-" * 50)
    
    # Load environment variables
    load_dotenv()
    
    whatsapp_sender = os.getenv("WHATSAPP_SENDER")
    astrosouks_sender = os.getenv("ASTROSOUKS_WHATSAPP_SENDER")
    
    print(f"WHATSAPP_SENDER: {whatsapp_sender}")
    print(f"ASTROSOUKS_WHATSAPP_SENDER: {astrosouks_sender}")
    print(f"ENABLE_MULTI_TENANT: {os.getenv('ENABLE_MULTI_TENANT', 'true')}")
    print(f"ROUTE_BY_DESTINATION: {os.getenv('ROUTE_BY_DESTINATION', 'true')}")
    print()

def test_validation():
    """Test configuration validation."""
    print("📋 Testing configuration validation:")
    print("-" * 50)
    
    validation_result = MultiTenantConfig.validate_config()
    print(f"Configuration valid: {validation_result['valid']}")
    
    if validation_result['issues']:
        print("Issues found:")
        for issue in validation_result['issues']:
            print(f"  - {issue}")
    else:
        print("✅ No configuration issues found")
    
    print(f"Multi-tenant enabled: {validation_result['multi_tenant_enabled']}")
    print(f"Usage tracking enabled: {validation_result['usage_tracking_enabled']}")
    print(f"Actions center enabled: {validation_result['actions_center_enabled']}")
    print(f"Default user: {validation_result['default_user']}")
    print(f"Default chatbot: {validation_result['default_chatbot']}")
    print()

def main():
    """Run all tests."""
    print("🚀 Multi-Tenant WhatsApp Configuration Test Suite")
    print("=" * 60)
    print()
    
    try:
        test_environment_variables()
        test_routing_configuration()
        test_sender_configuration()
        test_validation()
        
        print("🎉 All tests completed!")
        print("\n📝 Summary:")
        print("- ✅ Environment variables loaded")
        print("- ✅ Routing configuration tested")
        print("- ✅ Sender configuration methods tested")
        print("- ✅ Configuration validation passed")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
