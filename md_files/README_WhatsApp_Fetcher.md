# WhatsApp Message Fetcher for Infobip

A comprehensive Python solution for receiving and managing WhatsApp messages through Infobip's API using webhooks.

## 📋 Overview

This implementation provides a robust webhook server that:
- Receives WhatsApp messages from Infobip in real-time
- Stores messages in a SQLite database
- Provides REST API endpoints to query messages
- Includes authentication and error handling
- Supports message sending capabilities

## 🚀 Key Features

- **Real-time Message Reception**: Webhook server to receive messages instantly
- **Message Storage**: SQLite database with indexed searches
- **REST API**: Query messages programmatically
- **Statistics**: Track message counts and sender analytics
- **Message Sending**: Send WhatsApp messages through the API
- **Authentication**: Secure API key-based authentication
- **Error Handling**: Comprehensive logging and error management

## 📦 Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up Environment Variables**:
   ```bash
   cp env_template.txt .env
   ```
   Edit `.env` with your Infobip credentials:
   ```
   INFOBIP_API_KEY=your_infobip_api_key_here
   INFOBIP_BASE_URL=your_infobip_base_url_here
   WHATSAPP_SENDER=your_whatsapp_sender_number
   ```

3. **Get Your Infobip Credentials**:
   - Login to your Infobip account
   - Navigate to API settings to find your API key and base URL
   - Register a WhatsApp sender number

## ⚙️ Configuration

### 1. Infobip Web Interface Setup

1. **Login to Infobip**: Go to [Infobip Portal](https://portal.infobip.com)
2. **Navigate to WhatsApp**: Go to Channels > WhatsApp > Senders
3. **Configure Webhook**: 
   - Select your sender number
   - Click "Edit Configuration"
   - Set "Forwarding action" to "Forward to HTTP"
   - Enter your webhook URL: `https://your-domain.com/webhook/whatsapp`

### 2. Webhook URL Requirements

Your webhook URL must be:
- Publicly accessible (use ngrok for local testing)
- HTTPS enabled
- Able to receive POST requests

### 3. Local Development with ngrok

```bash
# Install ngrok
npm install -g ngrok

# In one terminal, run your webhook server
python whatsapp_message_fetcher.py

# In another terminal, expose it publicly
ngrok http 8000

# Use the ngrok URL in your Infobip configuration
```

## 🔧 Usage

### Running the Webhook Server

```bash
python whatsapp_message_fetcher.py
```

The server will start on `http://localhost:8000` and create a SQLite database `whatsapp_messages.db`.

### API Endpoints

#### 1. Webhook Endpoint (for Infobip)
- **POST** `/webhook/whatsapp` - Receives messages from Infobip

#### 2. Query Messages
- **GET** `/messages` - Get all messages
- **GET** `/messages?from_number=441234567890` - Get messages from specific number
- **GET** `/messages?limit=50` - Limit results

#### 3. Statistics
- **GET** `/messages/stats` - Get message statistics

#### 4. Send Message
- **POST** `/send_message` - Send WhatsApp message
```json
{
  "to_number": "441234567890",
  "message": "Hello from the API!"
}
```

#### 5. Health Check
- **GET** `/health` - Check server status

### Using the Python Client

```python
# Example usage
import asyncio
from usage_example import get_all_messages, get_message_stats

async def main():
    # Get all messages
    await get_all_messages()
    
    # Get statistics
    await get_message_stats()

asyncio.run(main())
```

## 📊 Database Schema

The SQLite database contains a `messages` table with:

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE NOT NULL,
    from_number TEXT NOT NULL,
    to_number TEXT NOT NULL,
    message_type TEXT NOT NULL,
    text TEXT,
    contact_name TEXT,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_payload TEXT
);
```

## 🔐 Authentication

The system uses Infobip's API key authentication:
- Header: `Authorization: App {your_api_key}`
- All outbound API calls are authenticated
- Environment variables keep credentials secure

## 🛠️ Message Processing Flow

1. **Message Received**: Infobip sends POST request to `/webhook/whatsapp`
2. **Validation**: Payload structure is validated
3. **Processing**: Message data is extracted and processed
4. **Storage**: Message is stored in SQLite database
5. **Logging**: Event is logged for monitoring

## 📝 Example Webhook Payload

```json
{
  "results": [
    {
      "messageId": "a28dd97c-1ffb-4fcf-99f1-0b557ed381da",
      "from": "441234567890",
      "to": "447860099299",
      "message": {
        "type": "text",
        "text": "Hello World!"
      },
      "contact": {
        "name": "John Doe"
      }
    }
  ]
}
```

## 🔍 Monitoring and Debugging

### Logs
The application provides comprehensive logging:
- Message reception
- Processing errors
- Database operations
- API calls

### Database Queries
```python
# Connect to database directly
import sqlite3
conn = sqlite3.connect('whatsapp_messages.db')
cursor = conn.cursor()

# Query recent messages
cursor.execute("SELECT * FROM messages ORDER BY received_at DESC LIMIT 10")
messages = cursor.fetchall()
```

## 🚨 Error Handling

The system handles various error scenarios:
- Invalid webhook payloads
- Database connection issues
- API authentication failures
- Network timeouts

## 📈 Scaling Considerations

For production use:
- Use PostgreSQL instead of SQLite
- Implement message queuing (Redis/RabbitMQ)
- Add horizontal scaling with load balancers
- Implement proper authentication for API endpoints
- Use environment-specific configurations

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For issues and questions:
1. Check the logs for error messages
2. Verify your Infobip configuration
3. Test webhook connectivity
4. Contact Infobip support for API issues

## 📚 Additional Resources

- [Infobip WhatsApp API Documentation](https://www.infobip.com/docs/whatsapp)
- [Infobip Authentication Guide](https://www.infobip.com/docs/essentials/api-essentials/api-authentication)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLite Documentation](https://sqlite.org/docs.html) 