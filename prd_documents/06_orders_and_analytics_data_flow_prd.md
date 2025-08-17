# Orders and Analytics Data Flow PRD

## Document Information
- **Version:** 1.0
- **Date:** January 2025
- **Status:** Implementation Complete
- **Author:** SwiftReplies.ai Development Team

## Executive Summary

This document provides a comprehensive technical specification of how orders and analytics data are captured, processed, and saved to the Supabase database within the SwiftReplies.ai WhatsApp automation platform. The implementation includes real-time order synchronization from Shopify to local database and AI-powered conversation analytics using GPT-4.1-nano.

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Order Data Flow](#order-data-flow)
3. [Analytics Data Flow](#analytics-data-flow)
4. [Database Schema](#database-schema)
5. [Implementation Details](#implementation-details)
6. [Error Handling & Recovery](#error-handling--recovery)
7. [Performance Considerations](#performance-considerations)
8. [Security & Privacy](#security--privacy)

## System Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   WhatsApp      │    │   LangChain      │    │   Supabase      │
│   Conversation  │───▶│   Agent with     │───▶│   Database      │
│                 │    │   Tools          │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   Shopify API    │
                       │   Integration    │
                       └──────────────────┘
```

### Data Flow Pipelines

1. **Order Pipeline**: WhatsApp → Agent → Shopify API → Supabase Database
2. **Analytics Pipeline**: WhatsApp → Agent → GPT-4.1-nano → Supabase Database

## Order Data Flow

### 1. Order Creation Trigger

**Location**: `src/tools/ecla_draft_order_tool.py`

When a customer provides complete order information through WhatsApp conversation, the LangChain agent invokes the `create_ecla_order` tool with the following parameters:

```python
@tool
def create_ecla_order(
    customer_email: str,
    customer_first_name: str,
    customer_last_name: str,
    customer_phone: str,
    shipping_address_line1: str,
    shipping_city: str,
    shipping_province: str,
    shipping_country: str,
    shipping_postal_code: str,
    product_selections: str,
    billing_same_as_shipping: bool = True,
    order_notes: str = "",
    send_confirmation: bool = True,
    *,
    config: RunnableConfig
) -> str:
```

### 2. Shopify Order Processing

The tool processes the order in the following sequence:

1. **Data Validation**: Validates all required customer and shipping information
2. **Product Parsing**: Extracts product selections and maps to Shopify variant IDs
3. **Order Creation**: Creates order in Shopify using their API
4. **Inventory Adjustment**: Updates inventory levels in Shopify

### 3. Database Synchronization

**Location**: `src/multi_tenant_database.py` - `save_order_to_db()` method

After successful Shopify order creation, the order data is immediately saved to Supabase:

```python
def save_order_to_db(self, contact_id: int, user_id: int, shopify_order_data: Dict[str, Any]) -> Optional[int]:
```

#### Database Operation Details

**Table**: `orders`

**SQL Query**:
```sql
INSERT INTO orders (contact_id, user_id, order_details, total_amount, status, created_at, updated_at)
VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
RETURNING id
```

**Data Mapping**:
- `contact_id`: The WhatsApp contact who placed the order
- `user_id`: The business owner (multi-tenant identifier)
- `order_details`: Complete Shopify order response as JSONB
- `total_amount`: Extracted from `shopify_order_data.order_data.total_price`
- `status`: Set to `'confirmed'` (since Shopify order was successful)

### 4. Context Injection

The order tool receives context through LangChain's `RunnableConfig`:

```python
metadata = config.get('metadata', {})
user_id = metadata.get('user_id')
contact_id = metadata.get('contact_id')
```

This metadata is injected by the agent worker in `whatsapp_message_fetcher_multitenant.py`:

```python
config = RunnableConfig(
    configurable={"thread_id": thread_id},
    metadata={
        "user_id": user_id,
        "contact_id": contact_id,
        "language": language,
        "from_number": from_number,
        "timestamp": datetime.now().isoformat(),
    }
)
```

## Analytics Data Flow

### 1. Analytics Trigger

**Location**: `whatsapp_message_fetcher_multitenant.py` - `agent_worker()` function

Analytics processing is triggered after each successful WhatsApp response:

```python
# 10. Launch analytics processing in the background (fire-and-forget)
final_state = agent_response.get('final_state')
if final_state and final_state.get('messages'):
    # Construct the analytics state with the required fields
    analytics_state = {
        'conversation_id': thread_id,
        'contact_id': contact_id,
        'messages': final_state.get('messages', [])
    }
    asyncio.create_task(analytics_processor.run_analytics_task(analytics_state))
```

### 2. LLM-Powered Analysis

**Location**: `src/analytics/processor.py` - `AnalyticsProcessor` class

The analytics processor uses GPT-4.1-nano with structured output to analyze conversations:

#### Analytics Model Configuration

```python
self.analytics_model = init_chat_model(
    model="gpt-4.1-nano",
    model_provider="openai",
    temperature=0.0,
    max_tokens=1000,
    api_key=settings.openai_api_key,
).with_structured_output(AnalyticsOutput)
```

#### Structured Analytics Output

```python
class AnalyticsOutput(BaseModel):
    lead_temperature: str  # 'Cold', 'Warm', or 'Hot'
    top_inquiry_topics: List[str]  # Main conversation topics
    csat_score: Optional[int]  # 1-5 satisfaction score
    product_interest: List[ProductInterest]  # Products and interest scores
    is_potential_conversion: bool  # Likelihood of sale
    is_resolved_by_ai: bool  # AI resolution success
```

### 3. Analytics Database Storage

**Location**: `src/multi_tenant_database.py` - `async_update_contact_analytics()` method

Analytics data is stored in the `contacts` table's `custom_fields` JSONB column:

#### Database Operation Details

**Table**: `contacts`

**SQL Query**:
```sql
UPDATE contacts
SET custom_fields = custom_fields || %s::jsonb,
    updated_at = CURRENT_TIMESTAMP
WHERE id = %s
```

**Storage Method**:
- Uses PostgreSQL JSONB merge operator (`||`) to append new analytics
- Preserves existing custom field data
- Asynchronous operation using `aiopg` for non-blocking execution

### 4. Analytics Processing Flow

1. **State Construction**: Message fetcher creates analytics state with required fields
2. **Conversation Formatting**: Messages are formatted for LLM analysis
3. **LLM Invocation**: GPT-4.1-nano analyzes conversation and returns structured data
4. **Database Update**: Analytics saved asynchronously to contact's custom_fields

## Database Schema

### Orders Table Structure

```sql
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_details JSONB NOT NULL,
    total_amount DECIMAL(10,2),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    currency VARCHAR(3) DEFAULT 'USD',
    payment_status VARCHAR(50) DEFAULT 'pending',
    shipping_address JSONB,
    order_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### Contacts Table (Analytics Storage)

```sql
CREATE TABLE contacts (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    thread_id VARCHAR(255),
    custom_fields JSONB DEFAULT '{}'::jsonb,  -- Analytics storage
    is_paused BOOLEAN DEFAULT false,
    last_interaction TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### Analytics Data Structure in custom_fields

```json
{
  "lead_temperature": "Hot",
  "top_inquiry_topics": ["product pricing", "shipping options"],
  "csat_score": 5,
  "product_interest": [
    {
      "product_name": "ECLA® Purple Corrector",
      "interest_score": 0.9
    }
  ],
  "is_potential_conversion": true,
  "is_resolved_by_ai": true,
  "last_analytics_update": "2025-01-06T22:46:22Z"
}
```

## Implementation Details

### Connection Management

**Database Connections**:
- **Synchronous**: Uses `psycopg2` for order saving (blocking operations)
- **Asynchronous**: Uses `aiopg` for analytics saving (non-blocking operations)
- **Connection String**: `DATABASE_URL` environment variable (Supabase)

### Transaction Management

**Orders**:
- Single transaction with commit/rollback
- Immediate consistency required
- Synchronous execution to ensure order integrity

**Analytics**:
- Fire-and-forget asynchronous processing
- Non-blocking to avoid delaying user responses
- Individual operation with error isolation

### Multi-Tenant Support

Both order and analytics operations include `user_id` for proper tenant isolation:

```python
# Orders
INSERT INTO orders (contact_id, user_id, ...)

# Analytics (via contact relationship)
UPDATE contacts SET custom_fields = ... WHERE id = contact_id
```

## Error Handling & Recovery

### Order Processing Errors

1. **Shopify API Failures**: Order tool returns error message to user
2. **Database Failures**: Logged as critical error, but Shopify order remains valid
3. **Data Validation**: Comprehensive validation before API calls
4. **Transaction Rollback**: Automatic rollback on database errors

### Analytics Processing Errors

1. **Missing Data**: Warning logged, process aborts gracefully
2. **LLM Failures**: Error logged, no impact on user experience
3. **Database Failures**: Error logged, analytics lost for that conversation
4. **State Construction**: Validation of required fields before processing

### Error Logging

```python
# Order errors (critical - affects user experience)
logger.error(f"Database error saving order: {e}", exc_info=True)

# Analytics errors (non-critical - background process)
logger.warning(f"Missing necessary data for analytics in state for thread_id: {thread_id}")
```

## Performance Considerations

### Order Processing

- **Synchronous**: Immediate processing required for order confirmation
- **Response Time**: ~2-5 seconds including Shopify API calls
- **Blocking**: User waits for complete order processing

### Analytics Processing

- **Asynchronous**: Non-blocking background processing
- **Response Time**: User receives immediate response
- **Processing Time**: ~3-10 seconds for LLM analysis
- **Parallel Execution**: Multiple analytics tasks can run concurrently

### Database Performance

- **Indexes**: Proper indexing on `contact_id`, `user_id` for fast lookups
- **JSONB**: Efficient storage and querying of structured data
- **Connection Pooling**: Managed by Supabase for optimal performance

## Security & Privacy

### Data Protection

1. **Encryption**: All data encrypted in transit and at rest (Supabase)
2. **Multi-Tenancy**: Strict user isolation through `user_id` filtering
3. **Access Control**: Database-level row-level security (RLS)
4. **API Security**: Shopify API credentials secured in environment variables

### PII Handling

1. **Customer Data**: Stored in Shopify and replicated to orders table
2. **Conversation Data**: Processed by OpenAI for analytics (review privacy policy)
3. **Phone Numbers**: Stored securely with proper access controls
4. **Analytics**: Aggregated insights, minimal PII retention

### Compliance Considerations

- **GDPR**: Customer data can be deleted from both Shopify and Supabase
- **Data Retention**: Analytics data stored indefinitely for business insights
- **Audit Trail**: All operations logged with timestamps and user context

## Future Enhancements

### Planned Improvements

1. **Order Items Table**: Detailed line item storage for advanced analytics
2. **Webhook Integration**: Real-time Shopify webhooks for order status updates
3. **Analytics Dashboard**: Frontend visualization of analytics data
4. **Batch Analytics**: Periodic re-analysis of historical conversations
5. **Advanced Metrics**: Revenue attribution, customer lifetime value calculations

### Scalability Considerations

1. **Database Partitioning**: By user_id for large-scale multi-tenancy
2. **Analytics Queue**: Redis-based queue for high-volume analytics processing
3. **Caching**: Redis caching for frequently accessed analytics data
4. **Read Replicas**: Separate read replicas for analytics queries

---

## Technical Support

For questions about this implementation, contact the SwiftReplies.ai development team or refer to the following resources:

- **Database Schema**: `/database_migration/scripts/`
- **Order Tool**: `/src/tools/ecla_draft_order_tool.py`
- **Analytics Processor**: `/src/analytics/processor.py`
- **Database Module**: `/src/multi_tenant_database.py`
- **Message Fetcher**: `/whatsapp_message_fetcher_multitenant.py`