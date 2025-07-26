#!/usr/bin/env python3
"""
Test Setup for WhatsApp Message Fetcher

This script verifies that your environment is properly configured
and all required dependencies are installed.
"""

import os
import sys
from pathlib import Path

def test_environment_variables():
    """Test that required environment variables are set"""
    print("Testing environment variables...")
    
    required_vars = [
        'INFOBIP_API_KEY',
        'INFOBIP_BASE_URL',
        'WHATSAPP_SENDER'
    ]
    
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value or value == f"your_{var.lower()}_here":
            missing_vars.append(var)
        else:
            print(f"✓ {var} is set")
    
    if missing_vars:
        print(f"✗ Missing or invalid environment variables: {', '.join(missing_vars)}")
        print("Please update your .env file with the correct values")
        return False
    
    return True

def test_dependencies():
    """Test that required dependencies are installed"""
    print("\nTesting Python dependencies...")
    
    required_packages = [
        'fastapi',
        'uvicorn',
        'pydantic',
        'requests',
        'python-dotenv',
        'aiohttp',
        'sqlite3'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'python-dotenv':
                import dotenv
                print(f"✓ {package} is installed")
            elif package == 'sqlite3':
                import sqlite3
                print(f"✓ {package} is installed")
            else:
                __import__(package)
                print(f"✓ {package} is installed")
        except ImportError:
            missing_packages.append(package)
            print(f"✗ {package} is not installed")
    
    if missing_packages:
        print(f"\nPlease install missing packages:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def test_file_structure():
    """Test that required files exist"""
    print("\nTesting file structure...")
    
    required_files = [
        'whatsapp_message_fetcher.py',
        'usage_example.py',
        'requirements.txt'
    ]
    
    missing_files = []
    
    for file in required_files:
        if Path(file).exists():
            print(f"✓ {file} exists")
        else:
            missing_files.append(file)
            print(f"✗ {file} is missing")
    
    if missing_files:
        print(f"Missing files: {', '.join(missing_files)}")
        return False
    
    return True

def test_basic_import():
    """Test that the main module can be imported"""
    print("\nTesting main module import...")
    
    try:
        # Test basic imports from the main module
        from whatsapp_message_fetcher import WhatsAppMessageFetcher, app
        print("✓ Main module imports successfully")
        
        # Test that the class can be instantiated (with env vars)
        if test_environment_variables():
            try:
                fetcher = WhatsAppMessageFetcher()
                print("✓ WhatsAppMessageFetcher can be instantiated")
                # Close the database connection
                fetcher.conn.close()
                return True
            except Exception as e:
                print(f"✗ Error creating WhatsAppMessageFetcher: {e}")
                return False
        else:
            print("⚠ Skipping instantiation test due to missing environment variables")
            return False
        
    except Exception as e:
        print(f"✗ Error importing main module: {e}")
        return False

def main():
    """Run all tests"""
    print("WhatsApp Message Fetcher - Setup Test")
    print("=" * 50)
    
    tests = [
        test_dependencies,
        test_file_structure,
        test_environment_variables,
        test_basic_import
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Your setup is ready.")
        print("\nNext steps:")
        print("1. Start the webhook server: python whatsapp_message_fetcher.py")
        print("2. Configure your Infobip webhook URL")
        print("3. Test with usage_example.py")
        return True
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        return False

if __name__ == "__main__":
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("Warning: python-dotenv not installed. Environment variables should be set manually.")
    
    success = main()
    sys.exit(0 if success else 1) 