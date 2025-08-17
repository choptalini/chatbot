# Target Architecture: Multi-Tenant SaaS Database Schema

## Overview
This document defines the complete target database architecture for SwiftReplies.ai, including all new tables, modified existing tables, relationships, and constraints required for multi-tenant SaaS operation.

## Architecture Principles

### 1. Multi-Tenancy Design
- **Complete Data Isolation**: Every business table includes `user_id` for tenant separation
- **Composite Unique Constraints**: Shared resources (phone numbers, etc.) unique per user
- **Row-Level Security**: Database-level enforcement of tenant isolation
- **Scalable Partitioning**: Ready for horizontal scaling by `user_id`

### 2. Subscription Flexibility
- **JSONB Configuration**: Custom feature flags and limits per user
- **Usage-Based Limits**: Daily and monthly limits with real-time tracking
- **Feature Granularity**: Enable/disable individual features per subscription
- **Billing Integration**: Support for custom pricing and billing cycles

### 3. Performance Optimization
- **Strategic Indexing**: Optimized indexes for multi-tenant queries
- **Efficient Relationships**: Minimal JOIN overhead for common operations
- **Query Patterns**: Designed for typical SaaS usage patterns
- **Caching Ready**: Structure supports efficient caching strategies

## Complete Schema Design

### 1. Core User Management

#### users
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    company_name VARCHAR(255),
    phone VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true
);
```

#### user_subscriptions
```sql
CREATE TABLE user_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_name VARCHAR(255) NOT NULL,
    subscription_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- Message Limits
    daily_message_limit INTEGER NOT NULL DEFAULT 100,
    monthly_message_limit INTEGER NOT NULL DEFAULT 3000,
    
    -- Campaign Limits
    daily_campaign_limit INTEGER NOT NULL DEFAULT 5,
    monthly_campaign_limit INTEGER NOT NULL DEFAULT 150,
    
    -- Billing Information
    billing_amount DECIMAL(10,2),
    billing_currency VARCHAR(3) DEFAULT 'USD',
    billing_cycle VARCHAR(20) DEFAULT 'monthly',
    
    -- Contract Terms
    contract_start_date DATE NOT NULL,
    contract_end_date DATE,
    auto_renew BOOLEAN DEFAULT false,
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 2. Multi-Chatbot Management

#### chatbots
```sql
CREATE TABLE chatbots (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    whatsapp_phone_number VARCHAR(255) UNIQUE,
    general_instructions TEXT,
    is_active BOOLEAN DEFAULT true,
    bot_status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### bot_knowledge_base
```sql
CREATE TABLE bot_knowledge_base (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chatbot_id INTEGER NOT NULL REFERENCES chatbots(id) ON DELETE CASCADE,
    category VARCHAR(100),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### conversation_instructions
```sql
CREATE TABLE conversation_instructions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chatbot_id INTEGER NOT NULL REFERENCES chatbots(id) ON DELETE CASCADE,
    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    instruction_text TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 3. Enhanced Existing Tables

#### contacts (Modified)
```sql
-- Current table + new columns
ALTER TABLE contacts ADD COLUMN user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE contacts ADD COLUMN chatbot_id INTEGER REFERENCES chatbots(id) ON DELETE SET NULL;
ALTER TABLE contacts ADD COLUMN tags JSONB DEFAULT '[]'::jsonb;
ALTER TABLE contacts ADD COLUMN custom_fields JSONB DEFAULT '{}'::jsonb;
ALTER TABLE contacts ADD COLUMN last_interaction TIMESTAMP WITH TIME ZONE;

-- Update constraints
ALTER TABLE contacts DROP CONSTRAINT contacts_phone_number_key;
ALTER TABLE contacts DROP CONSTRAINT contacts_thread_id_key;
ALTER TABLE contacts ADD CONSTRAINT unique_contact_per_user UNIQUE (user_id, phone_number);
ALTER TABLE contacts ADD CONSTRAINT unique_thread_per_user UNIQUE (user_id, thread_id);
```

#### messages (Modified)
```sql
-- Current table + new columns
ALTER TABLE messages ADD COLUMN user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE messages ADD COLUMN chatbot_id INTEGER NOT NULL REFERENCES chatbots(id) ON DELETE CASCADE;
ALTER TABLE messages ADD COLUMN is_from_human BOOLEAN DEFAULT false;
```

#### orders (Modified)
```sql
-- Current table + new columns
ALTER TABLE orders ADD COLUMN user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE orders ADD COLUMN chatbot_id INTEGER NOT NULL REFERENCES chatbots(id) ON DELETE CASCADE;
ALTER TABLE orders ADD COLUMN order_number VARCHAR(100) UNIQUE;
ALTER TABLE orders ADD COLUMN total_amount DECIMAL(10,2);
ALTER TABLE orders ADD COLUMN currency VARCHAR(3) DEFAULT 'USD';
ALTER TABLE orders ADD COLUMN payment_status VARCHAR(50) DEFAULT 'pending';
```

#### campaigns (Modified)
```sql
-- Current table + new columns
ALTER TABLE campaigns ADD COLUMN user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE campaigns ADD COLUMN chatbot_id INTEGER REFERENCES chatbots(id) ON DELETE SET NULL;
ALTER TABLE campaigns ADD COLUMN target_criteria JSONB DEFAULT '{}'::jsonb;
ALTER TABLE campaigns ADD COLUMN scheduled_at TIMESTAMP WITH TIME ZONE;
```

### 4. Human-in-the-Loop Actions Center

#### actions
```sql
CREATE TABLE actions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chatbot_id INTEGER NOT NULL REFERENCES chatbots(id) ON DELETE CASCADE,
    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    request_type VARCHAR(50) NOT NULL,
    request_details TEXT NOT NULL,
    context_data JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'approved', 'denied', 'expired')),
    user_response TEXT,
    auto_approve_similar BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by INTEGER REFERENCES users(id)
);
```

### 5. Enhanced E-commerce

#### order_items
```sql
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_name VARCHAR(255) NOT NULL,
    product_sku VARCHAR(100),
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price DECIMAL(10,2),
    total_price DECIMAL(10,2),
    metadata JSONB DEFAULT '{}'::jsonb
);
```

#### products
```sql
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    sku VARCHAR(100),
    price DECIMAL(10,2),
    description TEXT,
    image_url VARCHAR(500),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_sku_per_user UNIQUE (user_id, sku)
);
```

### 6. Usage Tracking & Analytics

#### usage_tracking
```sql
CREATE TABLE usage_tracking (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tracking_date DATE NOT NULL,
    daily_messages_sent INTEGER DEFAULT 0,
    daily_messages_received INTEGER DEFAULT 0,
    daily_campaigns_sent INTEGER DEFAULT 0,
    daily_campaign_messages INTEGER DEFAULT 0,
    live_takeovers_used INTEGER DEFAULT 0,
    actions_created INTEGER DEFAULT 0,
    api_calls_made INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, tracking_date)
);
```

#### monthly_usage_summary
```sql
CREATE TABLE monthly_usage_summary (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    total_messages_sent INTEGER DEFAULT 0,
    total_campaigns_sent INTEGER DEFAULT 0,
    total_orders_created INTEGER DEFAULT 0,
    total_revenue DECIMAL(10,2) DEFAULT 0,
    overage_messages INTEGER DEFAULT 0,
    overage_campaigns INTEGER DEFAULT 0,
    overage_cost DECIMAL(10,2) DEFAULT 0,
    avg_daily_messages DECIMAL(8,2),
    avg_conversion_rate DECIMAL(5,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, year, month)
);
```

#### analytics_events
```sql
CREATE TABLE analytics_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chatbot_id INTEGER REFERENCES chatbots(id) ON DELETE SET NULL,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 7. API & Integration Management

#### api_keys
```sql
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_name VARCHAR(100) NOT NULL,
    api_key_hash VARCHAR(255) NOT NULL,
    permissions JSONB DEFAULT '{}'::jsonb,
    last_used TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### webhooks
```sql
CREATE TABLE webhooks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chatbot_id INTEGER REFERENCES chatbots(id) ON DELETE CASCADE,
    url VARCHAR(500) NOT NULL,
    events JSONB NOT NULL,
    secret_token VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

## Subscription Configuration Schema

### Example subscription_config JSONB:
```json
{
  "features": {
    "core_features": {
      "chatbot_management": true,
      "contact_management": true,
      "message_history": true,
      "basic_analytics": true
    },
    "advanced_features": {
      "live_chat_takeover": true,
      "actions_center": true,
      "multi_chatbot": true,
      "campaign_management": true,
      "advanced_analytics": false
    },
    "premium_features": {
      "api_access": false,
      "webhooks": false,
      "white_label": false,
      "bulk_operations": true
    },
    "enterprise_features": {
      "dedicated_support": true,
      "priority_queue": true,
      "custom_reports": false,
      "sla_guarantee": false
    }
  },
  "limits": {
    "max_chatbots": 3,
    "max_contacts": 10000,
    "max_team_members": 5,
    "message_history_days": 365,
    "max_webhooks": 2,
    "max_api_keys": 1,
    "max_concurrent_conversations": 50,
    "max_actions_per_day": 20
  },
  "permissions": {
    "export_data": true,
    "delete_conversations": false,
    "manage_billing": true,
    "invite_team_members": true,
    "configure_integrations": false,
    "access_raw_logs": false
  },
  "custom_settings": {
    "branding": {
      "custom_logo": false,
      "custom_colors": false,
      "hide_powered_by": true
    },
    "support": {
      "priority_level": "standard",
      "dedicated_manager": false,
      "phone_support": true,
      "response_time_hours": 24
    },
    "integrations": ["shopify", "stripe"],
    "custom_fields": {
      "industry": "e-commerce",
      "company_size": "50-100",
      "use_case": "customer_support"
    }
  }
}
```

## Performance Indexes

### Essential Indexes
```sql
-- User-based queries
CREATE INDEX idx_contacts_user_id ON contacts(user_id);
CREATE INDEX idx_messages_user_id ON messages(user_id);
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_campaigns_user_id ON campaigns(user_id);
CREATE INDEX idx_actions_user_id ON actions(user_id);

-- Chatbot-based queries
CREATE INDEX idx_contacts_chatbot_id ON contacts(chatbot_id);
CREATE INDEX idx_messages_chatbot_id ON messages(chatbot_id);
CREATE INDEX idx_orders_chatbot_id ON orders(chatbot_id);

-- Time-based queries
CREATE INDEX idx_messages_sent_at ON messages(sent_at);
CREATE INDEX idx_usage_tracking_user_date ON usage_tracking(user_id, tracking_date);
CREATE INDEX idx_analytics_events_user_type ON analytics_events(user_id, event_type);

-- Multi-tenant composite indexes
CREATE INDEX idx_contacts_user_phone ON contacts(user_id, phone_number);
CREATE INDEX idx_contacts_user_thread ON contacts(user_id, thread_id);

-- Status and filtering indexes
CREATE INDEX idx_actions_status ON actions(status);
CREATE INDEX idx_actions_user_status ON actions(user_id, status);
CREATE INDEX idx_chatbots_user_active ON chatbots(user_id, is_active);
```

## Data Relationships

### Primary Relationships
- **users** → **user_subscriptions** (1:1)
- **users** → **chatbots** (1:many)
- **chatbots** → **contacts** (1:many)
- **contacts** → **messages** (1:many)
- **contacts** → **orders** (1:many)

### Cross-Tenant Isolation
- All business tables include `user_id`
- All queries MUST filter by `user_id`
- Composite unique constraints prevent conflicts
- Foreign keys maintain referential integrity within tenants

## Migration Considerations

### Backwards Compatibility
- Existing LangGraph tables unchanged
- Current data can be migrated to admin user
- Backend functions enhanced with default parameters
- WhatsApp integration requires minimal changes

### Performance Impact
- Additional JOINs on `user_id` (minimal overhead)
- Composite indexes maintain query performance
- Partitioning ready for horizontal scaling
- Caching strategies can optimize frequent queries

---

**Document Status**: Complete v1.0  
**Architecture Date**: December 2024  
**Review Cycle**: After each implementation phase  
**Approval**: Technical Lead, Database Administrator 