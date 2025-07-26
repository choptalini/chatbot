#!/usr/bin/env node

/**
 * WhatsApp Flow Endpoint Key Generator
 * 
 * Generates RSA private/public key pairs for WhatsApp Flow endpoint encryption.
 * Usage: node src/keyGenerator.js {passphrase}
 * 
 * ⚠️ WARNING: This is for prototyping only, not production ready.
 */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// Get passphrase from command line arguments
const passphrase = process.argv[2];

if (!passphrase) {
    console.error('❌ Error: Passphrase is required');
    console.log('Usage: node src/keyGenerator.js {passphrase}');
    console.log('Example: node src/keyGenerator.js "my-secret-passphrase"');
    process.exit(1);
}

console.log('🔐 Generating RSA key pair for WhatsApp Flow endpoint...');
console.log(`📝 Using passphrase: "${passphrase}"`);

try {
    // Generate RSA key pair (2048-bit)
    const { publicKey, privateKey } = crypto.generateKeyPairSync('rsa', {
        modulusLength: 2048,
        publicKeyEncoding: {
            type: 'spki',
            format: 'pem'
        },
        privateKeyEncoding: {
            type: 'pkcs1', // WhatsApp typically expects PKCS#1 format
            format: 'pem',
            cipher: 'aes-256-cbc',
            passphrase: passphrase
        }
    });

    // Create keys directory if it doesn't exist
    const keysDir = path.join(__dirname, '..', 'keys');
    if (!fs.existsSync(keysDir)) {
        fs.mkdirSync(keysDir, { recursive: true });
    }

    // Save keys to files
    const privateKeyPath = path.join(keysDir, 'private_key.pem');
    const publicKeyPath = path.join(keysDir, 'public_key.pem');

    fs.writeFileSync(privateKeyPath, privateKey);
    fs.writeFileSync(publicKeyPath, publicKey);

    console.log('✅ Key pair generated successfully!');
    console.log(`📁 Private key saved to: ${privateKeyPath}`);
    console.log(`📁 Public key saved to: ${publicKeyPath}`);
    
    console.log('\n🔧 Environment Variables Setup:');
    console.log('Add these to your .env file or environment:');
    console.log('\n' + '='.repeat(80));
    console.log(`PASSPHRASE="${passphrase}"`);
    console.log('');
    console.log('PRIVATE_KEY="' + privateKey.replace(/\n/g, '\\n') + '"');
    console.log('='.repeat(80));

    console.log('\n📋 Next Steps:');
    console.log('1. Copy the environment variables above to your .env file');
    console.log('2. Upload the public key to WhatsApp Business API');
    console.log('3. Configure your Flow endpoint URL');
    console.log('4. Implement your Flow logic in src/flow.js');

    console.log('\n📤 Public Key for WhatsApp Upload:');
    console.log('='.repeat(50));
    console.log(publicKey);
    console.log('='.repeat(50));

    // Generate example .env file
    const envContent = `# WhatsApp Flow Endpoint Configuration
# Generated on ${new Date().toISOString()}

PASSPHRASE="${passphrase}"

PRIVATE_KEY="${privateKey.replace(/\n/g, '\\n')}"

# Add your other environment variables here
# WHATSAPP_TOKEN=your_whatsapp_token
# WEBHOOK_VERIFY_TOKEN=your_webhook_verify_token
# PORT=3000
`;

    const envPath = path.join(__dirname, '..', '.env.example');
    fs.writeFileSync(envPath, envContent);
    console.log(`\n📝 Example .env file created at: ${envPath}`);

} catch (error) {
    console.error('❌ Error generating key pair:', error.message);
    process.exit(1);
} 