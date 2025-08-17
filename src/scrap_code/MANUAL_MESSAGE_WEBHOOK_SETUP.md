# 📨 Manual Message Webhook Setup - SwiftReplies.ai

## Overview

This document explains how the manual message system works in SwiftReplies.ai using HTTP webhooks for reliable and immediate message delivery to WhatsApp.

## Architecture

```
Frontend → Database → HTTP Webhook → WhatsApp Fetcher → WhatsApp API
```

## 🔧 How It Works

### 1. **Frontend Sends Manual Message**
When a user sends a manual message in the SwiftReplies frontend:

1. Message is saved to the database with `direction: 'manual'` and `status: 'pending'`
2. Frontend immediately sends HTTP webhook to WhatsApp fetcher
3. Real-time updates show the message in the conversation

### 2. **Webhook Processing**
The WhatsApp fetcher receives the webhook at:
```
POST https://first-logical-tadpole.ngrok-free.app/manual-message
```

**Payload Format:**
```json
{
  "message_id": 123,
  "contact_id": 18,
  "content_text": "Hello from SwiftReplies user",
  "chatbot_id": 1,
  "created_at": "2025-08-05T18:30:00.000Z"
}
```

### 3. **WhatsApp Delivery**
The fetcher:
1. Gets contact phone number from database
2. Sends message via WhatsApp API (Infobip)
3. Updates message status to `'sent'` or `'failed'`
4. Logs the delivery status

## 🚀 Benefits of This Approach

✅ **Immediate delivery** - No polling delays  
✅ **Reliable** - Direct HTTP call, no complex LISTEN/NOTIFY  
✅ **Scalable** - No server load from polling  
✅ **Simple** - Easy to debug and monitor  
✅ **Fault tolerant** - Message saved even if webhook fails  

## 📍 Endpoints

### Manual Message Webhook
```http
POST /manual-message
Content-Type: application/json

{
  "message_id": number,
  "contact_id": number, 
  "content_text": string,
  "chatbot_id": number,
  "created_at": string
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Manual message processed"
}
```

### Health Check
```http
GET /health
```

**Response includes:**
```json
{
  "manual_message_system": "HTTP webhook",
  "webhook_endpoint": "/manual-message"
}
```

## 🔗 ngrok Configuration

The system uses ngrok to expose the local WhatsApp fetcher to the internet:

**Current URL:** `https://first-logical-tadpole.ngrok-free.app`

**To update the webhook URL:**
1. Update the URL in `swiftreplies_frontend/lib/supabase/database.ts`
2. Search for: `https://first-logical-tadpole.ngrok-free.app/manual-message`
3. Replace with new ngrok URL

## 🧪 Testing

### Test Manual Message Flow:
1. Start WhatsApp fetcher: `python whatsapp_message_fetcher_multitenant.py`
2. Open SwiftReplies frontend
3. Pause a conversation
4. Send a manual message
5. Check WhatsApp fetcher logs for:
   ```
   📨 Received manual message via HTTP: {...}
   📤 Sending manual message 123 to WhatsApp
   ✅ Manual message 123 sent successfully to +1234567890
   ```

### Test Webhook Directly:
```bash
curl -X POST https://first-logical-tadpole.ngrok-free.app/manual-message \
  -H "Content-Type: application/json" \
  -d '{
    "message_id": 999,
    "contact_id": 18,
    "content_text": "Test webhook message",
    "chatbot_id": 1,
    "created_at": "2025-08-05T18:30:00.000Z"
  }'
```

## 🚨 Troubleshooting

### Frontend Issues:
- Check browser console for webhook errors
- Verify ngrok URL is accessible
- Check if CORS is properly configured

### WhatsApp Fetcher Issues:
- Check if `/manual-message` endpoint exists
- Verify Infobip API credentials
- Check contact exists in database
- Verify phone number format

### Database Issues:
- Check if message was saved with `direction: 'manual'`
- Verify contact_id exists
- Check message status updates

## 📊 Monitoring

### Key Metrics to Monitor:
- Webhook success rate
- Message delivery time (frontend → WhatsApp)
- Failed message count
- WhatsApp API response times

### Logs to Watch:
- `📨 Received manual message via HTTP` - Webhook received
- `📤 Sending manual message X to WhatsApp` - Processing
- `✅ Manual message X sent successfully` - Success
- `❌ Failed to send manual message` - Failure

## 🔄 Future Improvements

1. **Retry Logic** - Retry failed webhook calls
2. **Queue System** - Handle high volume of manual messages
3. **Rate Limiting** - Prevent spam/abuse
4. **Metrics Dashboard** - Real-time monitoring
5. **Multiple Webhook URLs** - Load balancing

---

**Last Updated:** August 5, 2025  
**Version:** 2.0.0  
**System:** Multi-tenant WhatsApp automation