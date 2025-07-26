# ECLA AI Customer Support Agent

A production-ready AI customer support agent for ECLA that provides comprehensive customer service including product inquiries, inventory management, and order processing with automatic inventory adjustments.

## 🚀 Features

- **AI-Powered Customer Support**: Intelligent responses to customer inquiries
- **Real-Time Inventory Management**: Check stock levels with visual confirmation
- **Order Processing**: Create real orders with automatic inventory adjustments
- **Product Catalog**: Browse and search ECLA products
- **Shopify Integration**: Full integration with Shopify for orders and inventory
- **Terminal Interface**: Easy-to-use terminal chat interface

## 📁 Project Structure

```
whatsapp_folder/
├── src/
│   ├── agent/
│   │   ├── core.py           # Main agent logic and coordination
│   │   └── hooks.py          # Agent hooks and event handling
│   ├── tools/
│   │   ├── ecla_draft_order_tool.py   # Order creation with inventory adjustment
│   │   ├── ecla_inventory_tool.py     # Inventory checking with images
│   │   └── rag_tool.py               # RAG search functionality
│   ├── config/
│   │   └── settings.py       # Configuration management
│   └── data/
│       └── knowledge_base.py # Knowledge base for RAG
├── shopify_method/
│   ├── client.py             # Shopify API client
│   ├── constants.py          # API constants and mutations
│   ├── utils.py              # Utility functions
│   ├── exceptions.py         # Custom exceptions
│   └── __init__.py          # Module initialization
├── terminal_chat.py          # Terminal interface for testing
├── requirements.txt          # Python dependencies
├── setup.py                  # Package setup
└── .gitignore               # Git ignore rules
```

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd whatsapp_folder
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Create a `.env` file in the root directory:
   ```env
   SHOPIFY_SHOP_DOMAIN=your-shop.myshopify.com
   SHOPIFY_ACCESS_TOKEN=your-access-token
   OPENAI_API_KEY=your-openai-api-key
   ```

## 🚀 Usage

### Terminal Interface

Run the terminal chat interface:
```bash
python terminal_chat.py
```

### Available Tools

The agent has access to these tools:

1. **RAG Search (`rag_tool`)**:
   - Search knowledge base for product information
   - Answer customer questions about ECLA products

2. **Inventory Check (`check_ecla_inventory`)**:
   - Check current stock levels
   - Generate inventory images for visual confirmation

3. **Order Creation (`create_ecla_order`)**:
   - Create real orders in Shopify
   - Automatically decrease inventory by ordered quantities
   - Handle customer information and shipping details

4. **Product Catalog (`get_ecla_product_catalog`)**:
   - Display available ECLA products
   - Show pricing and product keys

### Example Usage

```python
# Check inventory
result = check_ecla_inventory()

# Create an order
order_data = {
    "customer_email": "customer@example.com",
    "customer_first_name": "John",
    "customer_last_name": "Doe",
    "product_selections": '[{"product_key": "purple_corrector", "quantity": 1}]',
    "shipping_address_line1": "123 Main St",
    "shipping_city": "New York",
    # ... other required fields
}
result = create_ecla_order(**order_data)
```

## 📦 Available Products

- **ECLA® Purple Corrector** (`purple_corrector`) - $26.00
- **ECLA® Teeth Whitening Pen** (`whitening_pen`) - $20.00
- **ECLA® e20 Bionic⁺ Kit** (`e20_bionic_kit`) - $55.00

## 🔧 Configuration

### Settings

Configure the agent in `src/config/settings.py`:
- API endpoints
- Default values
- Tool configurations

### Shopify Integration

The `shopify_method/` directory contains:
- GraphQL mutations for orders and inventory
- API client with comprehensive error handling
- Utility functions for data processing

## 🎯 Key Features

### Order Processing
- Creates real orders in Shopify
- Automatically decreases inventory by ordered quantities
- Handles customer information and shipping details
- Provides detailed order confirmation

### Inventory Management
- Real-time stock level checking
- Visual inventory confirmation with images
- Automatic inventory adjustments after orders
- Integration with Shopify inventory system

### Customer Support
- AI-powered responses to customer inquiries
- Knowledge base integration for product information
- Comprehensive product catalog browsing

## 🛡️ Error Handling

The system includes comprehensive error handling:
- Graceful handling of API failures
- Detailed error messages for debugging
- Fallback mechanisms for critical operations
- Logging for monitoring and troubleshooting

## 🧪 Testing

The codebase has been thoroughly tested with:
- Real order creation and inventory adjustment
- Multi-product order processing
- Error handling scenarios
- PII compliance validation

## 📝 Contributing

1. Follow the existing code structure
2. Add proper error handling
3. Include comprehensive logging
4. Test all functionality thoroughly
5. Update documentation as needed

## 📄 License

This project is proprietary software for ECLA.

## 🔗 Support

For support or questions, please contact the development team.

---

**Status**: ✅ Production Ready  
**Last Updated**: January 2025  
**Version**: 1.0.0 