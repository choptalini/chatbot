-- ================================================================
-- PHASE 1: Create New Core Tables
-- ================================================================
-- This script creates the foundational tables for multi-tenant SaaS
-- Risk Level: Low
-- Rollback: DROP TABLE statements (see rollback script)
-- ================================================================

-- Enable UUID extension if not already enabled (optional for future use)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ================================================================
-- 1. USERS TABLE - Core tenant table
-- ================================================================
CREATE TABLE IF NOT EXISTS users (
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

-- Add indexes for users table
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- ================================================================
-- 2. USER_SUBSCRIPTIONS TABLE - Custom subscription management
-- ================================================================
CREATE TABLE IF NOT EXISTS user_subscriptions (
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

-- Add indexes for user_subscriptions table
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_active ON user_subscriptions(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_contract ON user_subscriptions(contract_start_date, contract_end_date);

-- ================================================================
-- 3. CHATBOTS TABLE - Multi-chatbot management
-- ================================================================
CREATE TABLE IF NOT EXISTS chatbots (
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

-- Add indexes for chatbots table
CREATE INDEX IF NOT EXISTS idx_chatbots_user_id ON chatbots(user_id);
CREATE INDEX IF NOT EXISTS idx_chatbots_user_active ON chatbots(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_chatbots_phone ON chatbots(whatsapp_phone_number);
CREATE INDEX IF NOT EXISTS idx_chatbots_status ON chatbots(bot_status);

-- ================================================================
-- 4. BOT_KNOWLEDGE_BASE TABLE - Custom Q&A for chatbots
-- ================================================================
CREATE TABLE IF NOT EXISTS bot_knowledge_base (
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

-- Add indexes for bot_knowledge_base table
CREATE INDEX IF NOT EXISTS idx_bot_knowledge_user_id ON bot_knowledge_base(user_id);
CREATE INDEX IF NOT EXISTS idx_bot_knowledge_chatbot_id ON bot_knowledge_base(chatbot_id);
CREATE INDEX IF NOT EXISTS idx_bot_knowledge_category ON bot_knowledge_base(category);
CREATE INDEX IF NOT EXISTS idx_bot_knowledge_active ON bot_knowledge_base(user_id, is_active);

-- ================================================================
-- 5. CONVERSATION_INSTRUCTIONS TABLE - Dynamic bot instructions
-- ================================================================
CREATE TABLE IF NOT EXISTS conversation_instructions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chatbot_id INTEGER NOT NULL REFERENCES chatbots(id) ON DELETE CASCADE,
    contact_id INTEGER, -- Will be linked after contacts table is modified
    instruction_text TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes for conversation_instructions table
CREATE INDEX IF NOT EXISTS idx_conv_instructions_user_id ON conversation_instructions(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_instructions_chatbot_id ON conversation_instructions(chatbot_id);
CREATE INDEX IF NOT EXISTS idx_conv_instructions_contact_id ON conversation_instructions(contact_id);
CREATE INDEX IF NOT EXISTS idx_conv_instructions_active ON conversation_instructions(is_active);
CREATE INDEX IF NOT EXISTS idx_conv_instructions_expires ON conversation_instructions(expires_at);

-- ================================================================
-- VALIDATION QUERIES
-- ================================================================
-- Verify all tables were created successfully
SELECT 
    schemaname, 
    tablename, 
    tableowner 
FROM pg_tables 
WHERE tablename IN ('users', 'user_subscriptions', 'chatbots', 'bot_knowledge_base', 'conversation_instructions')
    AND schemaname = 'public'
ORDER BY tablename;

-- Check table sizes (should be 0 for new tables)
SELECT 
    'users' as table_name, COUNT(*) as row_count FROM users
UNION ALL
SELECT 'user_subscriptions', COUNT(*) FROM user_subscriptions
UNION ALL
SELECT 'chatbots', COUNT(*) FROM chatbots
UNION ALL
SELECT 'bot_knowledge_base', COUNT(*) FROM bot_knowledge_base
UNION ALL
SELECT 'conversation_instructions', COUNT(*) FROM conversation_instructions;

-- ================================================================
-- SUCCESS CRITERIA CHECKLIST
-- ================================================================
-- [ ] All 5 new tables created successfully
-- [ ] All foreign key relationships established
-- [ ] All indexes created without errors
-- [ ] Tables are empty (row_count = 0)
-- [ ] Existing WhatsApp automation unaffected
-- ================================================================

PRINT 'Phase 1 migration completed successfully!'; 