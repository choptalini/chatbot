# WhatsApp Webhook Setup Guide

## ✅ Status: Your Webhook Server is Running!

Your webhook server is currently running on `http://localhost:8000` and is healthy.

## 🆕 NEW SUBSCRIPTION CONFIGURATION

**Your New Subscription Details:**
- Subscription ID: `40d4e135-9ce0-4681-9b95-f3ba8ee14430`
- Channel: WHATSAPP
- Events: INBOUND_MESSAGE
- Profile ID: whatsapp_message_2

**Current Webhook URL:** `https://7b0ce59adb1e.ngrok-free.app/webhook`

## 🔧 Available Endpoints

- **POST** `/webhook` - Receives WhatsApp messages from Infobip (UPDATED for new subscription)
- **GET** `/messages` - View all received messages
- **GET** `/messages/stats` - Message statistics
- **GET** `/health` - Server health check

## ⚙️ Configure Your New Subscription

**IMPORTANT:** You need to configure the webhook URL for your new subscription in Infobip:

1. **Go to your Infobip subscription** (the one shown in your screenshot)
2. **Click on the subscription** with ID `40d4e135-9ce0-4681-9b95-f3ba8ee14430`
3. **Set the webhook URL to:** `https://7b0ce59adb1e.ngrok-free.app/webhook`
4. **Save the configuration**

## 🌐 Making Your Webhook Publicly Accessible

### Option 1: ngrok (Recommended for Testing)

1. **Get ngrok v2 Auth Token**:
   - Go to https://dashboard.ngrok.com/get-started/your-authtoken
   - Sign up for a free account if you don't have one
   - **IMPORTANT**: Make sure you're getting a v2 authtoken (not v1)
   - Copy the authtoken that looks like: `2abcdefghijklmnopqrstuvwxyz_3AbCdEfGhIjKlMnOpQrStUvWxYz`

2. **Authenticate ngrok**:
   ```bash
   ngrok authtoken YOUR_V2_AUTH_TOKEN_HERE
   ```
   
   ⚠️ **Common Issue**: If you get "authentication failed: The authtoken you specified is an ngrok v1 authtoken", you need to get a new v2 token from the link above.

3. **Start the tunnel**:
   ```bash
   ngrok http 8000
   ```

4. **Get your webhook URL**:
   - ngrok will show you a URL like: `https://abc123.ngrok-free.app`
   - Your webhook URL will be: `https://abc123.ngrok-free.app/webhook`

### Option 2: Alternative Tunneling Services

#### Using Cloudflare Tunnel (Free)
```bash
# Install cloudflared
brew install cloudflared

# Start tunnel
cloudflared tunnel --url http://localhost:8000
```

#### Using Localtunnel (Free)
```bash
# Install localtunnel
npm install -g localtunnel

# Start tunnel
lt --port 8000
```

### Option 3: Deploy to Production

Deploy your webhook server to:
- **Heroku** (free tier available)
- **Railway** (free tier available)
- **DigitalOcean** App Platform
- **AWS** Lambda/EC2
- **Google Cloud Run**

## 🔗 Configure Infobip Webhook

1. **Login to Infobip Portal**: https://portal.infobip.com
2. **Navigate to**: Channels → WhatsApp → Senders
3. **Select your sender number**: 96179374241
4. **Click**: "Edit Configuration"
5. **In Inbound Configuration**:
   - Set "Forwarding action" to "Forward to HTTP"
   - Enter your webhook URL: `https://your-domain.com/webhook/whatsapp`
   - Set "Renderer" to "MO_OTT_CONTACT"
6. **Save Configuration**

## 🧪 Test Your Webhook

### 1. Send a Test Message
Send a WhatsApp message to your business number (96179374241) from another phone.

### 2. Check Received Messages
```bash
curl http://localhost:8000/messages
```

### 3. Check Statistics
```bash
curl http://localhost:8000/messages/stats
```

### 4. Test Webhook Endpoint
```bash
# Test with sample payload
curl -X POST http://localhost:8000/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "results": [{
      "messageId": "test-123",
      "from": "96170895652",
      "to": "96179374241",
      "message": {
        "type": "text",
        "text": "Hello test message"
      },
      "contact": {
        "name": "Test User"
      }
    }]
  }'
```

## 📱 Current Setup Summary

- **Webhook Server**: ✅ Running on localhost:8000
- **Health Status**: ✅ Healthy
- **Database**: ✅ SQLite initialized
- **Authentication**: ✅ API keys configured
- **Endpoints**: ✅ All working

## 🔍 Troubleshooting

### Common Issues:

1. **Webhook not receiving messages**:
   - Check if URL is publicly accessible
   - Verify HTTPS is used (required by Infobip)
   - Check Infobip configuration

2. **Messages not storing**:
   - Check server logs: `tail -f whatsapp_messages.log`
   - Verify database permissions

3. **Connection errors**:
   - Ensure port 8000 is not blocked
   - Check firewall settings

### Debug Commands:

```bash
# Check server status
curl http://localhost:8000/health

# View recent logs
python -c "
import sqlite3
conn = sqlite3.connect('whatsapp_messages.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM messages ORDER BY received_at DESC LIMIT 5')
for row in cursor.fetchall():
    print(row)
"

# Test webhook endpoint
curl -X POST http://localhost:8000/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{"results":[{"messageId":"test","from":"123","to":"456","message":{"type":"text","text":"test"}}]}'
```

## 📦 Next Steps

1. **Set up public URL** (ngrok/cloudflare/deploy)
2. **Configure Infobip webhook** with your public URL
3. **Send test messages** to verify everything works
4. **Monitor logs** for incoming messages

## 🎯 Your Webhook URL Format

Once you have a public URL, your webhook URL will be:
```
https://your-domain.com/webhook/whatsapp
```