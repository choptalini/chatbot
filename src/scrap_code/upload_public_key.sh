#!/bin/bash

# WhatsApp Flow Public Key Upload Script
# Phone Number ID: 1066845025621428

# Replace YOUR_ACCESS_TOKEN with your actual WhatsApp Business API access token
ACCESS_TOKEN="YOUR_ACCESS_TOKEN"

# Check if access token is set
if [ "$ACCESS_TOKEN" = "YOUR_ACCESS_TOKEN" ]; then
    echo "❌ Please set your actual access token in this script"
    echo "Edit this file and replace YOUR_ACCESS_TOKEN with your real token"
    exit 1
fi

echo "🔑 Uploading public key to WhatsApp Business API..."
echo "📱 Phone Number ID: 1066845025621428"

curl -X POST \
  "https://graph.facebook.com/v18.0/1066845025621428/whatsapp_business_encryption" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "business_public_key": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAhZFMCzY5RgFRDK6FKxTB\nEHRcsmGD6P+3s1elVJmD6/T54IbNMTbsREXDVT6p2bJrinKxdD/QSOjkVT9dDmsL\nw6OU3t+VTYoyvmUHbHW579n36xFAnO76+Nx/sm8Z8T9BIQVl2/T1aTg4l9DE+QG/\nwL9kmvnsFC3gSTBccKfCJTp6giSAMxteVC2koJs48daYaEoHXyxGI79ECJS6DZ9S\n7qKxBoaCxkA6Xmei7UQ8kNrFI20LE5WxM8L+OnW9xc4amUNi8t1NrD+GO0kA55M3\no0+IW/+7oLU7+J50ruky/m9vc1+jZJ+4JqL4hHWkCFw6t/3P/ILposp+PVTjQq6k\nywIDAQAB\n-----END PUBLIC KEY-----"
  }'

echo ""
echo "✅ Upload command completed"
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