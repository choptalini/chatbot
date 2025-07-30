#!/bin/bash

# WhatsApp Flow Public Key Upload Script
# Phone Number ID: 1066845025621428

# Access token is stored in a separate, non-committed file for security
if [ -f .access_token ]; then
    ACCESS_TOKEN=$(cat .access_token)
else
    echo "❌ Access token file (.access_token) not found."
    echo "Please create a file named .access_token with your token."
    exit 1
fi

echo "🔑 Uploading public key to WhatsApp Business API..."
echo "📱 Phone Number ID: 1066845025621428"

# Public key content
PUBLIC_KEY_CONTENT=$(cat keys/public_key.pem)

# API Request
curl -X POST \
  "https://graph.facebook.com/v18.0/1066845025621428/whatsapp_business_encryption" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"business_public_key\": \"$PUBLIC_KEY_CONTENT\"
  }"

echo ""
echo "✅ Upload command completed."
echo ""
echo "📋 Expected successful response:"
echo '{'
echo '  "success": true'
echo '}'
echo ""
echo "❌ If you get an error, check:"
echo "1. Your access token is valid and has proper permissions"
echo "2. The phone number ID (1066845025621428) is correct"
echo "3. Your WhatsApp Business Account is properly configured" 