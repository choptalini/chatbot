#!/bin/bash

# Final script to upload the WhatsApp Flow public key.
# This script cleans the access token before use.

echo "🔑 Uploading public key to WhatsApp Business API..."
echo "📱 Phone Number ID: 1066845025621428"

# Clean the access token by removing any whitespace
ACCESS_TOKEN=$(cat .access_token | tr -d '[:space:]')

# Get the public key content
PUBLIC_KEY=$(cat keys/public_key.pem)

# API Request
curl -X POST "https://graph.facebook.com/v18.0/1066845025621428/whatsapp_business_encryption" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"business_public_key\": \"$PUBLIC_KEY\"
  }"

echo ""
echo ""
echo "✅ If you see '{\"success\": true}', your key is uploaded and signed!" 