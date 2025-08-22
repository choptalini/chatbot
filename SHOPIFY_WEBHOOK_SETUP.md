# Shopify Webhook Integration Setup

This guide explains how to set up and use the Shopify webhook integration for automatically updating the bot knowledge base when products are created, updated, or deleted.

## Overview

The integration consists of:
1. A webhook endpoint (`/webhook/shopify`) that receives Shopify product events
2. HMAC signature verification for security
3. Background processing that saves product information to the `bot_knowledge_base` table
4. GraphQL scripts to register webhooks with Shopify

## Setup Instructions

### 1. Environment Configuration

Add these environment variables to your `.env` file:

```bash
# Shopify Configuration
SHOPIFY_SHOP_DOMAIN=your-shop.myshopify.com
SHOPIFY_ACCESS_TOKEN=your_admin_api_access_token
SHOPIFY_WEBHOOK_SECRET=your_webhook_secret_key

# Database (already configured)
DATABASE_URL=your_postgresql_connection_string
```

### 2. Get Your Webhook Secret

When you create webhooks using the GraphQL script, Shopify will provide a webhook secret. You can also set a custom secret when creating the webhook subscription.

### 3. Register Webhooks with Shopify

Use the provided script to register webhooks:

```bash
# Setup webhooks (replace with your actual webhook URL)
python scripts/setup_shopify_webhooks.py --webhook-url https://your-app.onrender.com/webhook/shopify --action setup

# List existing webhooks
python scripts/setup_shopify_webhooks.py --action list

# Clean up old webhooks
python scripts/setup_shopify_webhooks.py --action cleanup
```

### 4. Test the Integration

Run the test script to verify the webhook endpoint works:

```bash
# Make sure your server is running first
python whatsapp_message_fetcher.py

# In another terminal, run the tests
python scripts/test_shopify_webhook.py
```

## How It Works

### Webhook Endpoint (`/webhook/shopify`)

1. **Receives webhook**: Accepts POST requests from Shopify
2. **Verifies signature**: Uses HMAC-SHA256 to verify the request is from Shopify
3. **Processes asynchronously**: Responds immediately to Shopify, processes in background
4. **Updates knowledge base**: Saves product info to `bot_knowledge_base` table

### Supported Events

- `products/create` - New product created
- `products/update` - Existing product updated  
- `products/delete` - Product deleted

### Knowledge Base Integration

For each product event, the system creates a Q&A entry in the knowledge base:

**Question**: "What is [Product Name]?"

**Answer**: "[Product Name] is a [product_type] product by [vendor]. Prices: [variant_prices]. Description: [clean_description]..."

For deleted products, the answer indicates the product is discontinued.

## Security Features

- **HMAC Verification**: All requests must have valid Shopify HMAC signature
- **Header Validation**: Requires proper Shopify headers
- **Error Handling**: Graceful handling of malformed requests

## Monitoring and Logging

The webhook endpoint logs:
- Successful webhook receipts
- HMAC verification results
- Background processing status
- Database operations
- Any errors or failures

Check your application logs for webhook activity:

```bash
tail -f logs/agent.log | grep "Shopify\|webhook/shopify"
```

## Database Schema

Product information is stored in the `bot_knowledge_base` table:

```sql
INSERT INTO bot_knowledge_base (
    user_id,           -- Bot owner's user ID
    chatbot_id,        -- Chatbot ID
    category,          -- e.g., "product_info_create"
    question,          -- e.g., "What is Amazing Product?"
    answer,            -- Product description and details
    is_active          -- true
);
```

## Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check `SHOPIFY_WEBHOOK_SECRET` matches the secret used when creating webhooks
   - Verify HMAC signature is being calculated correctly

2. **400 Bad Request**
   - Missing required headers (`X-Shopify-Topic`, `X-Shopify-Hmac-Sha256`)
   - Invalid JSON payload

3. **500 Internal Server Error**
   - Database connection issues
   - Missing environment variables
   - Check application logs for details

### Testing Locally

1. Use ngrok to expose your local server:
   ```bash
   ngrok http 8000
   ```

2. Use the ngrok URL when setting up webhooks:
   ```bash
   python scripts/setup_shopify_webhooks.py --webhook-url https://your-ngrok-url.ngrok.io/webhook/shopify
   ```

3. Test with the provided test script:
   ```bash
   python scripts/test_shopify_webhook.py
   ```

## GraphQL Webhook Management

### Create Webhook Subscription

```graphql
mutation webhookSubscriptionCreate($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
  webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
    userErrors {
      field
      message
    }
    webhookSubscription {
      id
      topic
      format
      endpoint {
        __typename
        ... on WebhookHttpEndpoint {
          callbackUrl
        }
      }
    }
  }
}
```

Variables:
```json
{
  "topic": "PRODUCTS_CREATE",
  "webhookSubscription": {
    "callbackUrl": "https://your-app.onrender.com/webhook/shopify",
    "format": "JSON"
  }
}
```

### List Webhooks

```graphql
query {
  webhookSubscriptions(first: 50) {
    edges {
      node {
        id
        topic
        format
        endpoint {
          __typename
          ... on WebhookHttpEndpoint {
            callbackUrl
          }
        }
      }
    }
  }
}
```

### Delete Webhook

```graphql
mutation webhookSubscriptionDelete($id: ID!) {
  webhookSubscriptionDelete(id: $id) {
    userErrors {
      field
      message
    }
    deletedWebhookSubscriptionId
  }
}
```

## Production Considerations

1. **Rate Limiting**: Shopify may send webhooks in bursts; ensure your server can handle multiple concurrent requests

2. **Idempotency**: Consider implementing idempotency keys to handle duplicate webhook deliveries

3. **Filtering**: You may want to filter webhooks by specific user/shop instead of updating all chatbots

4. **Error Handling**: Implement retry logic for failed database operations

5. **Monitoring**: Set up alerts for webhook failures or high error rates

## Files Modified/Created

- `whatsapp_message_fetcher.py` - Added webhook endpoint and processing functions
- `src/multi_tenant_database.py` - Added knowledge base methods
- `scripts/setup_shopify_webhooks.py` - Webhook registration script
- `scripts/test_shopify_webhook.py` - Testing script
- `SHOPIFY_WEBHOOK_SETUP.md` - This documentation

## Support

If you encounter issues:
1. Check the application logs
2. Verify environment variables are set correctly
3. Test with the provided test script
4. Ensure your webhook URL is publicly accessible
5. Verify Shopify app permissions include webhook access