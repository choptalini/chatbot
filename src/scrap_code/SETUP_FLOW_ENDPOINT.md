# WhatsApp Flow Endpoint Setup Guide

Complete guide to set up and test your WhatsApp Flow endpoint using the generated RSA keys.

## 🚀 Quick Setup

### Step 1: Install Dependencies

```bash
pip install -r requirements_flow.txt
```

### Step 2: Generate RSA Keys (if not done already)

```bash
node src/keyGenerator.js "your-secure-passphrase"
```

### Step 3: Configure Environment

The keys are automatically configured in `.env.flow`. Optionally, add your Facebook App Secret:

```bash
# Edit .env.flow and replace:
APP_SECRET="your-facebook-app-secret-here"
```

### Step 4: Start the Endpoint Server

```bash
python start_flow_endpoint.py
```

### Step 5: Test the Endpoint

```bash
python test_flow_endpoint.py
```

## 📍 Your Endpoint URLs

- **Ngrok Public URL**: `https://first-logical-tadpole.ngrok-free.app/ecla_flow`
- **Local URL**: `http://localhost:8080/ecla_flow`

## 🔑 Public Key for WhatsApp

Upload this public key to WhatsApp Business API:

```
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAhZFMCzY5RgFRDK6FKxTB
EHRcsmGD6P+3s1elVJmD6/T54IbNMTbsREXDVT6p2bJrinKxdD/QSOjkVT9dDmsL
w6OU3t+VTYoyvmUHbHW579n36xFAnO76+Nx/sm8Z8T9BIQVl2/T1aTg4l9DE+QG/
wL9kmvnsFC3gSTBccKfCJTp6giSAMxteVC2koJs48daYaEoHXyxGI79ECJS6DZ9S
7qKxBoaCxkA6Xmei7UQ8kNrFI20LE5WxM8L+OnW9xc4amUNi8t1NrD+GO0kA55M3
o0+IW/+7oLU7+J50ruky/m9vc1+jZJ+4JqL4hHWkCFw6t/3P/ILposp+PVTjQq6k
ywIDAQAB
-----END PUBLIC KEY-----
```

## 📱 WhatsApp Flow Configuration

### Method 1: Via API

When creating your Flow via API, set:

```json
{
  "data_api_version": "3.0",
  "endpoint_uri": "https://first-logical-tadpole.ngrok-free.app/ecla_flow"
}
```

### Method 2: Via WhatsApp Manager

1. Go to WhatsApp Manager → Flows
2. Edit your Flow
3. Connect Meta App to the Flow
4. Set endpoint URL: `https://first-logical-tadpole.ngrok-free.app/ecla_flow`

## 🔐 How the Encryption Works

### Request Flow
1. **WhatsApp encrypts** AES key with your public key (RSA-OAEP-SHA256)
2. **WhatsApp encrypts** Flow data with AES key (AES-GCM)
3. **Your endpoint** decrypts AES key with private key
4. **Your endpoint** decrypts Flow data with AES key

### Response Flow
1. **Your endpoint** processes the request
2. **Your endpoint** encrypts response with same AES key (flipped IV)
3. **WhatsApp** decrypts your response

## 🏗️ Flow Logic Structure

The endpoint handles these Flow screens:

- **WELCOME**: Introduction and navigation options
- **PRODUCT_SELECTION**: Choose ECLA products  
- **CUSTOMER_INFO**: Collect customer details
- **CONFIRMATION**: Review and confirm order

### Flow Actions Supported:
- `INIT`: Flow initialization
- `data_exchange`: Screen submissions
- `BACK`: Back button navigation
- `ping`: Health checks

## 🧪 Testing Your Setup

### 1. Local Testing
```bash
# Start the server
python start_flow_endpoint.py

# In another terminal, run tests
python test_flow_endpoint.py
```

### 2. Health Check Endpoints
- **Local**: http://localhost:8080/health
- **Public**: https://first-logical-tadpole.ngrok-free.app/health

### 3. Manual Testing with cURL

```bash
# Test health endpoint
curl https://first-logical-tadpole.ngrok-free.app/health

# Test basic connectivity
curl -X POST https://first-logical-tadpole.ngrok-free.app/ecla_flow \
  -H "Content-Type: application/json" \
  -d '{"test": "connectivity"}'
```

## 🔧 WhatsApp Business API Setup

### Upload Public Key

#### For Cloud API:
```bash
curl -X POST \
  https://graph.facebook.com/v18.0/{phone-number-id}/whatsapp_business_encryption \
  -H "Authorization: Bearer {access-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "business_public_key": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
  }'
```

#### For On-Prem API (v2.51.x+):
```bash
curl -X POST \
  https://your-onprem-api.com/v1/settings/business/profile \
  -H "Authorization: Bearer {auth-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "business_public_key": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
  }'
```

## 🔄 Flow Completion Handling

When a Flow completes, your endpoint sends:

```json
{
  "screen": "SUCCESS",
  "data": {
    "extension_message_response": {
      "params": {
        "flow_token": "your-flow-token",
        "customer_name": "John Doe",
        "customer_email": "john@example.com",
        "product": "e20_bionic_kit",
        "completion_time": "2024-01-20T15:30:00Z"
      }
    }
  }
}
```

This data is forwarded to your webhook as a Flow completion message.

## 🐛 Troubleshooting

### Common Issues

1. **Decryption Failed (HTTP 421)**
   - Check if private key matches uploaded public key
   - Verify passphrase is correct
   - Ensure proper key format (PKCS#1)

2. **Invalid Signature (HTTP 401)**
   - Set correct `APP_SECRET` in `.env.flow`
   - Ensure Facebook App Secret matches

3. **Connection Refused**
   - Check if server is running on port 8080
   - Verify ngrok tunnel is active
   - Test with local health endpoint first

### Debug Mode

Enable detailed logging:

```bash
# Add to .env.flow
LOG_LEVEL=DEBUG
```

### Key Regeneration

If you need new keys:

```bash
# Generate new key pair
node src/keyGenerator.js "new-passphrase"

# Update .env.flow with new keys
# Re-upload public key to WhatsApp
```

## 📊 Flow Analytics

Monitor your Flow performance:

```bash
# Check server logs
tail -f logs/flow-endpoint.log

# Monitor health endpoint
watch -n 30 curl https://first-logical-tadpole.ngrok-free.app/health
```

## 🔒 Security Best Practices

1. **Never expose private key**
2. **Use strong passphrases**
3. **Implement signature validation**
4. **Monitor for failed decryption attempts**
5. **Rotate keys periodically**
6. **Use HTTPS in production**

## 📚 Additional Resources

- [WhatsApp Flows Documentation](https://developers.facebook.com/docs/whatsapp/flows)
- [Encryption Examples](https://developers.facebook.com/docs/whatsapp/flows/guides/implement-endpoint#code-examples)
- [Flow Builder UI](https://business.facebook.com/wa/flows)

---

✅ **Your WhatsApp Flow endpoint is ready!**

**Endpoint URL**: `https://first-logical-tadpole.ngrok-free.app/ecla_flow`

Next: Upload your public key to WhatsApp Business API and test with a real Flow. 