# WhatsApp Flow Endpoint Key Generator

This guide explains how to generate RSA key pairs for WhatsApp Flow endpoints, following the method described in the official WhatsApp Flow Endpoint documentation.

⚠️ **WARNING**: This project is meant to be an example for prototyping only. It's not production ready.

## Quick Start

### 1. Generate RSA Key Pair

Run the key generator script with your chosen passphrase:

```bash
node src/keyGenerator.js "your-secret-passphrase"
```

**Example:**
```bash
node src/keyGenerator.js "my-secret-passphrase-123"
```

### 2. What Gets Generated

The script creates:
- `keys/private_key.pem` - Your encrypted private key (keep secret!)
- `keys/public_key.pem` - Your public key (upload to WhatsApp)
- `.env.example` - Environment variables template

### 3. Copy Environment Variables

Copy the generated environment variables to your `.env` file:

```bash
cp .env.example .env
```

Your `.env` file will contain:
```env
PASSPHRASE="your-secret-passphrase"
PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...your encrypted key...\n-----END RSA PRIVATE KEY-----\n"
```

## File Structure

```
whatsapp_folder/
├── src/
│   ├── keyGenerator.js          # Key generation script
│   └── flow.js                  # Flow logic template
├── keys/
│   ├── private_key.pem          # Your private key (encrypted)
│   └── public_key.pem           # Your public key (for WhatsApp)
├── .env                         # Your environment variables
└── .env.example                 # Generated template
```

## Key Generation Process

### What the Script Does

1. **Generates RSA Key Pair**: Creates 2048-bit RSA keys using Node.js crypto module
2. **Encrypts Private Key**: Uses AES-256-CBC encryption with your passphrase
3. **Saves Key Files**: Stores both keys in `keys/` directory
4. **Creates Environment Template**: Generates `.env.example` with proper formatting
5. **Displays Instructions**: Shows next steps and public key for upload

### Key Format Details

- **Private Key**: PKCS#1 format, AES-256-CBC encrypted
- **Public Key**: SPKI format, PEM encoded
- **Key Size**: 2048-bit (recommended for WhatsApp)

## Usage Example

```bash
# Generate keys
$ node src/keyGenerator.js "super-secret-passphrase"

🔐 Generating RSA key pair for WhatsApp Flow endpoint...
📝 Using passphrase: "super-secret-passphrase"
✅ Key pair generated successfully!
📁 Private key saved to: /path/to/keys/private_key.pem
📁 Public key saved to: /path/to/keys/public_key.pem

🔧 Environment Variables Setup:
Add these to your .env file or environment:

================================================================================
PASSPHRASE="super-secret-passphrase"

PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...encrypted key...\n-----END RSA PRIVATE KEY-----\n"
================================================================================

📤 Public Key for WhatsApp Upload:
==================================================
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
...your public key...
ywIDAQAB
-----END PUBLIC KEY-----
==================================================
```

## Next Steps After Key Generation

### 1. Upload Public Key to WhatsApp

You need to upload the public key to WhatsApp Business API. The exact process depends on your setup:

#### For Cloud API:
- Use WhatsApp Business API to upload the public key
- The key will be automatically signed by WhatsApp

#### For On-Prem API (v2.51.x+):
- Use the On-Prem API endpoint to upload the public key
- Ensure you're using version 2.51.x or higher

### 2. Set Up Your Flow Endpoint

Configure your endpoint URL in your Flow configuration:
```
https://yourdomain.com/flow-endpoint
```

### 3. Implement Flow Logic

Edit `src/flow.js` to implement your specific Flow screens and navigation logic.

### 4. Environment Variables

Add additional environment variables as needed:
```env
PASSPHRASE="your-secret-passphrase"
PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...your encrypted key...\n-----END RSA PRIVATE KEY-----\n"

# Additional variables for your endpoint
WHATSAPP_TOKEN=your_whatsapp_token
WEBHOOK_VERIFY_TOKEN=your_webhook_verify_token
PORT=3000
```

## Security Best Practices

### Key Management
- **Keep private key secret**: Never commit `keys/private_key.pem` to version control
- **Use strong passphrases**: Choose complex, unique passphrases
- **Dedicated keys per WABA**: Use separate key pairs for each WhatsApp Business Account
- **Regular rotation**: Consider rotating keys periodically

### Environment Variables
- **Use .env files**: Keep sensitive data in environment variables
- **Don't commit .env**: Add `.env` to your `.gitignore`
- **Escape line breaks**: Ensure `\n` in PRIVATE_KEY for multiline keys

### Production Considerations
- **Use secure key storage**: Consider using AWS KMS, Azure Key Vault, etc.
- **Implement proper logging**: Log key usage without exposing key data
- **Monitor for alerts**: Watch for public-key-missing or signature-verification errors

## When to Re-generate Keys

You need to create new keys and re-upload in these scenarios:

1. **Number re-registration**: When you re-register your WhatsApp Business number
2. **Platform migration**: When migrating between On-Prem ↔ Cloud API
3. **Key compromise**: If your private key is potentially compromised
4. **Error alerts**: When receiving these webhook alerts:
   - `public-key-missing`
   - `public-key-signature-verification`

## Flow Logic Template

The included `src/flow.js` provides a template for implementing your Flow logic:

```javascript
const { handleDataExchange, handleHealthCheck, handleErrorNotification } = require('./src/flow');

// Handle different Flow actions
function processFlowRequest(decryptedData) {
    const { action } = decryptedData;
    
    switch (action) {
        case 'INIT':
        case 'data_exchange':
        case 'BACK':
            return handleDataExchange(decryptedData);
        case 'ping':
            return handleHealthCheck();
        default:
            return handleErrorNotification(decryptedData);
    }
}
```

## Troubleshooting

### Common Issues

1. **"Cannot find module" error**
   ```bash
   # Ensure you're in the correct directory
   cd /path/to/whatsapp_folder
   node src/keyGenerator.js "passphrase"
   ```

2. **Permission denied**
   ```bash
   # Make script executable
   chmod +x src/keyGenerator.js
   ```

3. **Environment variable format issues**
   ```bash
   # Ensure proper escaping of newlines
   PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nProc-Type: 4,ENCRYPTED\n..."
   ```

### Validation

Verify your setup:
```bash
# Check if keys exist
ls -la keys/

# Verify public key format
cat keys/public_key.pem

# Test environment variables
source .env && echo "Passphrase: $PASSPHRASE"
```

## Related Documentation

- [WhatsApp Flows Endpoint Documentation](https://developers.facebook.com/docs/whatsapp/flows/guides/implement-endpoint)
- [WhatsApp Business API Reference](https://developers.facebook.com/docs/whatsapp/cloud-api)
- [Encryption/Decryption Examples](https://developers.facebook.com/docs/whatsapp/flows/guides/implement-endpoint#code-examples)

---

**Note**: This implementation is based on the official WhatsApp Flow Endpoint Server example and follows the same key generation patterns used in Meta's documentation. 