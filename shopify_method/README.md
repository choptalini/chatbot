# Shopify Method Library

A comprehensive Python library for Shopify GraphQL Admin API integration, designed specifically for AI agents and chatbots.

## 🚀 Features

- **Complete GraphQL API Coverage**: All major Shopify operations including inventory, orders, products, customers, and locations
- **AI Agent Ready**: Designed for seamless integration with LangChain and other AI frameworks
- **Error Resilient**: Comprehensive error handling with automatic retry mechanisms
- **Special Operations**: Combined operations like creating draft orders with automatic inventory adjustments
- **Type Hints**: Full type annotation support for better IDE experience
- **Standardized Responses**: Consistent response format across all methods

## 📦 Installation

```bash
pip install -e .
```

### Dependencies

- `requests>=2.25.0` - HTTP requests
- `python-dotenv>=0.19.0` - Environment variable management

### Optional Dependencies

```bash
# For AI agent integration
pip install -e .[langchain]

# For development
pip install -e .[dev]
```

## 🔧 Quick Start

### 1. Basic Setup

```python
from shopify_method import ShopifyClient

# Initialize client
client = ShopifyClient(
    shop_domain="your-shop.myshopify.com",
    access_token="your-access-token",
    api_version="2024-10"  # optional, defaults to 2024-10
)

# Health check
health = client.health_check()
if health['success']:
    print(f"Connected to {health['data']['shop']['name']}")
```

### 2. Environment Variables

Create a `.env` file:

```env
SHOPIFY_SHOP_DOMAIN=your-shop.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_your_access_token_here
```

```python
import os
from dotenv import load_dotenv
from shopify_method import ShopifyClient

load_dotenv()

client = ShopifyClient(
    shop_domain=os.getenv('SHOPIFY_SHOP_DOMAIN'),
    access_token=os.getenv('SHOPIFY_ACCESS_TOKEN')
)
```

## 📚 Core Methods

### Inventory Management

```python
# Get inventory for a variant
inventory = client.get_inventory(variant_id="123456789")
if inventory['success']:
    for location in inventory['data']['locations']:
        print(f"{location['location_name']}: {location['available']} units")

# Adjust inventory (increase/decrease)
result = client.adjust_inventory(
    variant_id="123456789",
    quantity_change=-5,  # Decrease by 5
    reason="correction"
)

# Set absolute inventory level
result = client.set_inventory(
    variant_id="123456789",
    quantity=100,
    reason="restock"
)
```

### Product Operations

```python
# Get all products
products = client.get_products(limit=10, search="keyword")

# Get specific product details
product = client.get_product(product_id="123456789")

# Get product variants
variants = client.get_product_variants(product_id="123456789")
```

### Order Operations

```python
# Create draft order
line_items = [
    {
        'variantId': '123456789',
        'quantity': 2
    }
]

draft_order = client.create_draft_order(line_items)

# Create real order (requires write_orders permission)
order = client.create_order(line_items, customer_info={
    'email': 'customer@example.com'
})

# Get order details
order_details = client.get_order_details(order_id="123456789")
```

### 🎯 Special Operations

#### Create Draft Order + Inventory Adjustment

The most powerful feature - creates a draft order and automatically decreases inventory:

```python
result = client.create_draft_order_with_inventory_adjustment(
    variant_id="123456789",
    quantity=1,
    customer_info={'email': 'customer@example.com'},
    reason="correction"
)

if result['success']:
    data = result['data']
    
    # Draft order info
    print(f"Draft Order: {data['draft_order']['name']}")
    print(f"Total: ${data['draft_order']['total_price']}")
    
    # Inventory adjustment info
    inv = data['inventory_adjustment']
    print(f"Inventory: {inv['previous_quantity']} → {inv['quantity_after_change']}")
    
    # Summary
    summary = data['operation_summary']
    print(f"Reserved {summary['inventory_reserved']} units")
```

### Location Operations

```python
# Get all locations
locations = client.get_locations()

# Get inventory for specific location
location_inventory = client.get_location_inventory(
    location_id="123456789",
    variant_id="987654321"
)
```

### Bulk Operations

```python
# Bulk inventory adjustments
adjustments = [
    {"variant_id": "123", "quantity_change": -1, "reason": "correction"},
    {"variant_id": "456", "quantity_change": 5, "reason": "restock"},
    {"variant_id": "789", "quantity_change": -2, "reason": "damaged"}
]

bulk_result = client.bulk_adjust_inventory(adjustments)
print(f"Successful: {bulk_result['data']['successful_count']}")
print(f"Failed: {bulk_result['data']['failed_count']}")
```

## 🤖 AI Agent Integration

### LangChain Tools

```python
from langchain.tools import Tool
from shopify_method import ShopifyClient

client = ShopifyClient(shop_domain="...", access_token="...")

def get_inventory_tool(variant_id: str) -> str:
    """Get inventory levels for a product variant."""
    result = client.get_inventory(variant_id=variant_id)
    if result['success']:
        locations = result['data']['locations']
        return f"Inventory: {locations[0]['available']} units available"
    return f"Error: {result['error']}"

def create_draft_order_tool(variant_id: str, quantity: int = 1) -> str:
    """Create a draft order and adjust inventory."""
    result = client.create_draft_order_with_inventory_adjustment(
        variant_id=variant_id,
        quantity=quantity
    )
    if result['success']:
        data = result['data']
        return f"Created {data['draft_order']['name']} and reserved {quantity} units"
    return f"Error: {result['error']}"

# Create LangChain tools
inventory_tool = Tool(
    name="get_inventory",
    description="Get inventory levels for a product variant",
    func=get_inventory_tool
)

order_tool = Tool(
    name="create_draft_order",
    description="Create a draft order and automatically adjust inventory",
    func=create_draft_order_tool
)

tools = [inventory_tool, order_tool]
```

## ⚡ Response Format

All methods return a standardized response:

```python
{
    "success": bool,           # Operation success status
    "data": dict,             # Response data (if successful)
    "error": str,             # Error message (if failed)
    "api_cost": int,          # GraphQL API cost
    "timestamp": str          # ISO timestamp
}
```

## 🔐 Required Permissions

Your Shopify app needs these scopes:

### Minimum Required:
- `read_products` - Read product information
- `read_inventory` - Read inventory levels

### For Full Functionality:
- `write_inventory` - Adjust inventory levels
- `write_draft_orders` - Create draft orders
- `read_draft_orders` - Read draft order details
- `write_orders` - Create real orders (optional)
- `read_orders` - Read order details (optional)
- `read_locations` - Access location information

## 📊 API Usage Monitoring

```python
# Track API usage
usage = client.get_api_usage()
print(f"API calls made: {usage['data']['calls_made']}")
print(f"Total cost: {usage['data']['total_cost_used']}")
print(f"Average cost per call: {usage['data']['average_cost_per_call']}")
```

## 🛡️ Error Handling

The library provides specific exception types:

```python
from shopify_method import (
    ShopifyClient,
    ShopifyAPIError,
    RateLimitError,
    PermissionError,
    ValidationError
)

try:
    result = client.get_inventory(variant_id="invalid")
except PermissionError as e:
    print(f"Permission denied: {e}")
except RateLimitError as e:
    print(f"Rate limited: {e}")
except ValidationError as e:
    print(f"Validation error: {e}")
except ShopifyAPIError as e:
    print(f"API error: {e}")
```

## 🧪 Testing

```bash
# Run unit tests
pytest tests/

# Run with coverage
pytest tests/ --cov=shopify_method

# Run specific test file
pytest tests/test_client.py -v
```

## 🚀 Advanced Usage

### Custom Configuration

```python
client = ShopifyClient(
    shop_domain="shop.myshopify.com",
    access_token="token",
    api_version="2024-10"
)

# The client automatically handles:
# - Rate limiting with exponential backoff
# - API cost tracking
# - Error classification and retry logic
# - GraphQL query optimization
```

### Inventory Reasons

Valid reasons for inventory adjustments:

```python
VALID_REASONS = [
    'correction', 'cycle_count_available', 'damaged',
    'movement_created', 'movement_updated', 'movement_received',
    'movement_canceled', 'other', 'promotion', 'quality_control',
    'received', 'reservation_created', 'reservation_deleted',
    'reservation_updated', 'restock', 'safety_stock', 'shrinkage'
]
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run the test suite
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 📞 Support

For issues and questions:
- Check existing issues on GitHub
- Create a new issue with detailed information
- Include error messages and steps to reproduce

---

**Made with ❤️ for AI developers working with Shopify** 