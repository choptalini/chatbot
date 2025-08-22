#!/bin/bash

# Set environment variables for local testing
export SHOPIFY_WEBHOOK_SECRET="test-webhook-secret-for-local-development"

# You can add other environment variables here as needed
# export SHOPIFY_SHOP_DOMAIN="your-shop.myshopify.com"
# export SHOPIFY_ACCESS_TOKEN="your_access_token"

echo "Starting server with environment variables..."
echo "SHOPIFY_WEBHOOK_SECRET is set: $(if [ -n "$SHOPIFY_WEBHOOK_SECRET" ]; then echo "✅"; else echo "❌"; fi)"

# Start the server
python whatsapp_message_fetcher.py