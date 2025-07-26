#!/usr/bin/env python3
"""
WhatsApp Flow Endpoint Startup Script

This script loads the .env.flow file and starts the FastAPI server.
Usage: python start_flow_endpoint.py
"""

import os
import sys
from dotenv import load_dotenv

# Load the Flow-specific environment file
load_dotenv('.env.flow')

# Verify required environment variables
required_vars = ['PRIVATE_KEY', 'PASSPHRASE']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print(f"❌ Missing required environment variables: {missing_vars}")
    print("Please ensure .env.flow contains PRIVATE_KEY and PASSPHRASE")
    sys.exit(1)

print("✅ Environment variables loaded successfully")
print(f"🔑 Private key loaded: {'✅' if os.getenv('PRIVATE_KEY') else '❌'}")
print(f"🔐 Passphrase set: {'✅' if os.getenv('PASSPHRASE') else '❌'}")
print(f"🛡️ App secret set: {'✅' if os.getenv('APP_SECRET') else '❌'}")

# Import and run the FastAPI app
if __name__ == "__main__":
    try:
        from whatsapp_flow_endpoint import app
        import uvicorn
        
        port = int(os.getenv("PORT", 8080))
        print(f"🚀 Starting WhatsApp Flow Endpoint Server on port {port}")
        print(f"📍 Flow endpoint: https://first-logical-tadpole.ngrok-free.app/ecla_flow")
        print(f"🌐 Local endpoint: http://localhost:{port}/ecla_flow")
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info"
        )
    except ImportError as e:
        print(f"❌ Failed to import WhatsApp Flow endpoint: {e}")
        print("Please install dependencies: pip install -r requirements_flow.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1) 