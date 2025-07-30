#!/bin/bash

# WhatsApp Access Token Debug Script (v2)
# This script helps verify the permissions and associations of your access token.

# Read access token from the secure file
if [ -f .access_token ]; then
    ACCESS_TOKEN=$(cat .access_token)
else
    echo "❌ Access token file (.access_token) not found."
    exit 1
fi

# Get the App ID and App Token from your Facebook Developer App dashboard
# App Token is generated as "App Secret" and can be found under App Settings -> Basic
# It's usually in the format: {app-id}|{app-secret}
CORRECT_APP_TOKEN="1095803192492789|4855d6cabdffb2b5fbc12ad8520e2847"

if [ "$CORRECT_APP_TOKEN" = "YOUR_APP_TOKEN_HERE" ]; then
    echo "❌ Please set your App Token in this script."
    echo "Go to your Facebook App -> Settings -> Basic -> App Secret"
    echo "Your App Token should be in the format: {app-id}|{app-secret}"
    exit 1
fi


echo "🔍 Debugging access token..."

curl -X GET \
  "https://graph.facebook.com/debug_token?input_token=$ACCESS_TOKEN&access_token=$CORRECT_APP_TOKEN"

echo ""
echo ""
echo "📋 How to interpret the results:"
echo "1. 'app_id': Should match your WhatsApp Business App's ID."
echo "2. 'business.id': Should match your WhatsApp Business Account ID."
echo "3. 'scopes': Must contain 'whatsapp_business_management' and 'whatsapp_business_messaging'."
echo ""
echo "If any of these are incorrect, you will need to generate a new token with the correct permissions." 