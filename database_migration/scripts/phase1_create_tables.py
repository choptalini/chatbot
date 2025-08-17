import psycopg2
import os
from dotenv import load_dotenv
import logging
from datetime import datetime

# Load environment variables from a .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def connect_to_db(db_url):
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(db_url)
        logger.info("Successfully connected to the database.")
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Error: Could not connect to the database. {e}")
        return None

def execute_phase1_migration(conn):
    """Executes Phase 1 migration: Create new core tables."""
    
    # Create tables SQL statements
    create_tables_sql = """
-- Enable UUID extension if not already enabled (optional for future use)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. USERS TABLE - Core tenant table
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

-- 2. USER_SUBSCRIPTIONS TABLE - Custom subscription management
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

-- 3. CHATBOTS TABLE - Multi-chatbot management
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

-- 4. BOT_KNOWLEDGE_BASE TABLE - Custom Q&A for chatbots
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

-- 5. CONVERSATION_INSTRUCTIONS TABLE - Dynamic bot instructions
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
"""

    # Create indexes SQL statements
    create_indexes_sql = """
-- Add indexes for users table
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- Add indexes for user_subscriptions table
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_active ON user_subscriptions(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_contract ON user_subscriptions(contract_start_date, contract_end_date);

-- Add indexes for chatbots table
CREATE INDEX IF NOT EXISTS idx_chatbots_user_id ON chatbots(user_id);
CREATE INDEX IF NOT EXISTS idx_chatbots_user_active ON chatbots(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_chatbots_phone ON chatbots(whatsapp_phone_number);
CREATE INDEX IF NOT EXISTS idx_chatbots_status ON chatbots(bot_status);

-- Add indexes for bot_knowledge_base table
CREATE INDEX IF NOT EXISTS idx_bot_knowledge_user_id ON bot_knowledge_base(user_id);
CREATE INDEX IF NOT EXISTS idx_bot_knowledge_chatbot_id ON bot_knowledge_base(chatbot_id);
CREATE INDEX IF NOT EXISTS idx_bot_knowledge_category ON bot_knowledge_base(category);
CREATE INDEX IF NOT EXISTS idx_bot_knowledge_active ON bot_knowledge_base(user_id, is_active);

-- Add indexes for conversation_instructions table
CREATE INDEX IF NOT EXISTS idx_conv_instructions_user_id ON conversation_instructions(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_instructions_chatbot_id ON conversation_instructions(chatbot_id);
CREATE INDEX IF NOT EXISTS idx_conv_instructions_contact_id ON conversation_instructions(contact_id);
CREATE INDEX IF NOT EXISTS idx_conv_instructions_active ON conversation_instructions(is_active);
CREATE INDEX IF NOT EXISTS idx_conv_instructions_expires ON conversation_instructions(expires_at);
"""
    
    try:
        with conn.cursor() as cur:
            logger.info("Starting Phase 1 migration: Creating new core tables...")
            
            # Execute table creation
            logger.info("Creating tables...")
            cur.execute(create_tables_sql)
            
            # Execute index creation
            logger.info("Creating indexes...")
            cur.execute(create_indexes_sql)
            
            # Commit all changes
            conn.commit()
            logger.info("Phase 1 migration completed successfully!")
            
            # Run validation queries
            logger.info("Running validation queries...")
            
            # Check if tables were created
            cur.execute("""
                SELECT 
                    schemaname, 
                    tablename, 
                    tableowner 
                FROM pg_tables 
                WHERE tablename IN ('users', 'user_subscriptions', 'chatbots', 'bot_knowledge_base', 'conversation_instructions')
                    AND schemaname = 'public'
                ORDER BY tablename;
            """)
            
            tables = cur.fetchall()
            logger.info(f"Created tables: {[table[1] for table in tables]}")
            
            # Check table row counts (should be 0)
            cur.execute("""
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
            """)
            
            row_counts = cur.fetchall()
            logger.info("Table row counts:")
            for table_name, count in row_counts:
                logger.info(f"  {table_name}: {count} rows")
            
            return True
            
    except psycopg2.Error as e:
        logger.error(f"Error during Phase 1 migration: {e}")
        conn.rollback()
        return False

def validate_existing_tables(conn):
    """Validates that existing tables are still intact."""
    try:
        with conn.cursor() as cur:
            # Check existing tables
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('contacts', 'messages', 'orders', 'campaigns', 'campaign_subscribers')
                ORDER BY table_name;
            """)
            
            existing_tables = cur.fetchall()
            logger.info(f"Existing tables validated: {[table[0] for table in existing_tables]}")
            
            # Check row counts to ensure no data loss
            cur.execute("""
                SELECT 'contacts' as table_name, COUNT(*) as record_count FROM contacts
                UNION ALL
                SELECT 'messages', COUNT(*) FROM messages
                UNION ALL
                SELECT 'orders', COUNT(*) FROM orders
                UNION ALL
                SELECT 'campaigns', COUNT(*) FROM campaigns
                UNION ALL
                SELECT 'campaign_subscribers', COUNT(*) FROM campaign_subscribers;
            """)
            
            counts = cur.fetchall()
            logger.info("Existing table row counts:")
            for table_name, count in counts:
                logger.info(f"  {table_name}: {count} rows")
            
            return True
            
    except psycopg2.Error as e:
        logger.error(f"Error validating existing tables: {e}")
        return False

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("PHASE 1 MIGRATION: Create New Core Tables")
    logger.info("=" * 60)
    
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        logger.error("Error: DATABASE_URL environment variable is not set.")
        logger.error("Please set it before running the script.")
        logger.error('Example: export DATABASE_URL="postgresql://user:password@host:port/dbname"')
        exit(1)
    
    # Connect to database
    connection = connect_to_db(db_url)
    if not connection:
        exit(1)
    
    try:
        # Validate existing tables before migration
        logger.info("Step 1: Validating existing tables...")
        if not validate_existing_tables(connection):
            logger.error("Existing table validation failed. Aborting migration.")
            exit(1)
        
        # Execute Phase 1 migration
        logger.info("Step 2: Executing Phase 1 migration...")
        if not execute_phase1_migration(connection):
            logger.error("Phase 1 migration failed.")
            exit(1)
        
        # Final validation
        logger.info("Step 3: Final validation...")
        if not validate_existing_tables(connection):
            logger.error("Post-migration validation failed.")
            exit(1)
        
        logger.info("=" * 60)
        logger.info("✅ PHASE 1 MIGRATION COMPLETED SUCCESSFULLY!")
        logger.info("✅ New core tables created: users, user_subscriptions, chatbots")
        logger.info("✅ All existing tables preserved")
        logger.info("✅ Ready for Phase 2: Modify existing tables")
        logger.info("=" * 60)
        
    finally:
        connection.close()
        logger.info("Database connection closed.") 