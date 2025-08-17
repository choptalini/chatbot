#!/usr/bin/env python3
"""
Test Script for SwiftReplies.ai Multi-Tenant System
Validates that the new multi-tenant database and bot system is working correctly
"""

import sys
import logging
from datetime import datetime
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_database_connection():
    """Test 1: Database connectivity"""
    logger.info("🔍 Testing database connection...")
    try:
        from src.multi_tenant_database import db
        conn = db.connect_to_db()
        if conn:
            conn.close()
            logger.info("✅ Database connection: SUCCESS")
            return True
        else:
            logger.error("❌ Database connection: FAILED")
            return False
    except Exception as e:
        logger.error(f"❌ Database connection error: {e}")
        return False

def test_configuration():
    """Test 2: Configuration validation"""
    logger.info("🔍 Testing configuration...")
    try:
        from src.multi_tenant_config import config
        validation = config.validate_config()
        
        if validation['valid']:
            logger.info("✅ Configuration: VALID")
            logger.info(f"   Multi-tenant enabled: {validation['multi_tenant_enabled']}")
            logger.info(f"   Usage tracking enabled: {validation['usage_tracking_enabled']}")
            logger.info(f"   Actions center enabled: {validation['actions_center_enabled']}")
            return True
        else:
            logger.error(f"❌ Configuration issues: {validation['issues']}")
            return False
    except Exception as e:
        logger.error(f"❌ Configuration error: {e}")
        return False

def test_user_mapping():
    """Test 3: User phone number mapping"""
    logger.info("🔍 Testing user mapping...")
    try:
        from src.multi_tenant_database import get_user_by_phone_number
        
        test_phone = "+1234567890"
        user_info = get_user_by_phone_number(test_phone)
        
        if user_info and 'user_id' in user_info and 'chatbot_id' in user_info:
            logger.info(f"✅ User mapping: SUCCESS")
            logger.info(f"   Phone {test_phone} → User {user_info['user_id']}, Chatbot {user_info['chatbot_id']}")
            return True
        else:
            logger.error("❌ User mapping: FAILED - Invalid response")
            return False
    except Exception as e:
        logger.error(f"❌ User mapping error: {e}")
        return False

def test_database_operations():
    """Test 4: Database operations"""
    logger.info("🔍 Testing database operations...")
    try:
        from src.multi_tenant_database import db
        
        # Test contact creation (using SwiftReplies admin - user_id=2)
        test_phone = "+1999888777"
        contact_id, thread_id = db.get_or_create_contact(test_phone, user_id=2, name="Test Contact")
        
        if contact_id and thread_id:
            logger.info(f"✅ Contact creation: SUCCESS (ID: {contact_id})")
            
            # Test message logging (with unique message ID)
            import time
            unique_msg_id = f"test_msg_{int(time.time())}"
            success = db.log_message(
                contact_id=contact_id,
                message_id=unique_msg_id,
                direction="incoming",
                message_type="text",
                content_text="Test message",
                chatbot_id=2  # SwiftReplies main bot
            )
            
            if success:
                logger.info("✅ Message logging: SUCCESS")
                
                # Test usage tracking (using SwiftReplies admin)
                track_success = db.track_usage(user_id=2, messages_sent=1)
                if track_success:
                    logger.info("✅ Usage tracking: SUCCESS")
                    return True
                else:
                    logger.error("❌ Usage tracking: FAILED")
                    return False
            else:
                logger.error("❌ Message logging: FAILED")
                return False
        else:
            logger.error("❌ Contact creation: FAILED")
            return False
            
    except Exception as e:
        logger.error(f"❌ Database operations error: {e}")
        return False

def test_limits_checking():
    """Test 5: Usage limits checking"""
    logger.info("🔍 Testing usage limits...")
    try:
        from src.multi_tenant_database import check_message_limits
        
        limits_info = check_message_limits(user_id=2)
        
        if isinstance(limits_info, dict) and 'within_limits' in limits_info:
            logger.info(f"✅ Limits checking: SUCCESS")
            logger.info(f"   Within limits: {limits_info['within_limits']}")
            logger.info(f"   Usage: {limits_info.get('usage', {})}")
            return True
        else:
            logger.error("❌ Limits checking: FAILED - Invalid response")
            return False
    except Exception as e:
        logger.error(f"❌ Limits checking error: {e}")
        return False

def test_admin_user():
    """Test 6: Admin user and subscription"""
    logger.info("🔍 Testing admin user setup...")
    try:
        from src.multi_tenant_database import db
        conn = db.connect_to_db()
        
        if not conn:
            logger.error("❌ Admin user test: Database connection failed")
            return False
        
        try:
            with conn.cursor() as cur:
                # Check SwiftReplies admin user (user_id=2)
                cur.execute("SELECT id, email, full_name FROM users WHERE id = 2;")
                admin = cur.fetchone()
                
                if admin:
                    logger.info(f"✅ SwiftReplies admin found: {admin[2]} ({admin[1]})")
                    
                    # Check SwiftReplies admin subscription
                    cur.execute("""
                        SELECT subscription_name, daily_message_limit, is_active 
                        FROM user_subscriptions WHERE user_id = 2;
                    """)
                    subscription = cur.fetchone()
                    
                    if subscription:
                        logger.info(f"✅ SwiftReplies subscription: {subscription[0]} (Limit: {subscription[1]})")
                        return True
                    else:
                        logger.error("❌ SwiftReplies subscription: NOT FOUND")
                        return False
                else:
                    logger.error("❌ SwiftReplies admin user: NOT FOUND")
                    return False
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"❌ Admin user test error: {e}")
        return False

def test_table_structure():
    """Test 7: Database table structure"""
    logger.info("🔍 Testing database table structure...")
    try:
        from src.multi_tenant_database import db
        conn = db.connect_to_db()
        
        if not conn:
            logger.error("❌ Table structure test: Database connection failed")
            return False
        
        try:
            with conn.cursor() as cur:
                # Check for key tables
                expected_tables = [
                    'users', 'user_subscriptions', 'chatbots', 'contacts', 
                    'messages', 'orders', 'campaigns', 'actions', 'usage_tracking'
                ]
                
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name;
                """)
                
                existing_tables = [row[0] for row in cur.fetchall()]
                missing_tables = [table for table in expected_tables if table not in existing_tables]
                
                if not missing_tables:
                    logger.info(f"✅ Table structure: SUCCESS ({len(existing_tables)} tables)")
                    return True
                else:
                    logger.error(f"❌ Missing tables: {missing_tables}")
                    return False
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"❌ Table structure test error: {e}")
        return False

def run_all_tests() -> Dict[str, bool]:
    """Run all tests and return results"""
    logger.info("🚀 Starting SwiftReplies.ai Multi-Tenant System Tests")
    logger.info("=" * 60)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Configuration", test_configuration),
        ("User Mapping", test_user_mapping),
        ("Database Operations", test_database_operations),
        ("Usage Limits", test_limits_checking),
        ("Admin User Setup", test_admin_user),
        ("Table Structure", test_table_structure)
    ]
    
    results = {}
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running: {test_name}")
        try:
            result = test_func()
            results[test_name] = result
            if result:
                passed += 1
        except Exception as e:
            logger.error(f"❌ {test_name}: EXCEPTION - {e}")
            results[test_name] = False
    
    logger.info("\n" + "=" * 60)
    logger.info("📊 TEST RESULTS SUMMARY")
    logger.info("=" * 60)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} {test_name}")
    
    logger.info(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 ALL TESTS PASSED! Your multi-tenant system is ready!")
        return True
    else:
        logger.error(f"⚠️  {total - passed} tests failed. Please review the issues above.")
        return False

def main():
    """Main test execution"""
    try:
        success = run_all_tests()
        
        if success:
            logger.info("\n✅ Multi-tenant system validation: SUCCESS")
            logger.info("🚀 You can now start using the new WhatsApp message fetcher!")
            sys.exit(0)
        else:
            logger.error("\n❌ Multi-tenant system validation: FAILED")
            logger.error("🔧 Please fix the issues above before using the new system.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n💥 Unexpected error during testing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 