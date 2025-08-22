#!/usr/bin/env python3
"""
Simple script to test if environment variables are being loaded correctly.
"""

import os
from dotenv import load_dotenv

# Load environment variables (if .env file exists)
load_dotenv()

# Test the Shopify webhook secret
shopify_secret = os.getenv("SHOPIFY_WEBHOOK_SECRET", "")

print("Environment Variable Test")
print("=" * 30)
print(f"SHOPIFY_WEBHOOK_SECRET: {'✅ SET' if shopify_secret else '❌ NOT SET'}")
if shopify_secret:
    print(f"Value: {shopify_secret[:10]}...{shopify_secret[-4:] if len(shopify_secret) > 14 else shopify_secret}")
else:
    print("Value: (empty)")

# Test other related variables
other_vars = [
    "SHOPIFY_SHOP_DOMAIN",
    "SHOPIFY_ACCESS_TOKEN",
    "DATABASE_URL"
]

print("\nOther Variables:")
for var in other_vars:
    value = os.getenv(var, "")
    status = "✅ SET" if value else "❌ NOT SET"
    print(f"{var}: {status}")