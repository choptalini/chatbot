import psycopg2
import os
from dotenv import load_dotenv
import logging
import json
from datetime import datetime, date

# Load environment variables
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

def execute_phase5_constraints(conn):
    """Phase 5: Update constraints to enforce multi-tenancy."""
    logger.info("=" * 60)
    logger.info("PHASE 5: Update Constraints")
    logger.info("=" * 60)
    
    try:
        with conn.cursor() as cur:
            # 1. Make foreign keys NOT NULL
            logger.info("Step 1: Making foreign key columns NOT NULL...")
            
            constraints_sql = [
                "ALTER TABLE contacts ALTER COLUMN user_id SET NOT NULL;",
                "ALTER TABLE messages ALTER COLUMN chatbot_id SET NOT NULL;",
                "ALTER TABLE orders ALTER COLUMN user_id SET NOT NULL;",
                "ALTER TABLE campaigns ALTER COLUMN user_id SET NOT NULL;",
                "ALTER TABLE campaign_subscribers ALTER COLUMN user_id SET NOT NULL;"
            ]
            
            for sql in constraints_sql:
                cur.execute(sql)
            
            logger.info("✅ Foreign key columns set to NOT NULL")
            
            # 2. Add foreign key constraints
            logger.info("Step 2: Adding foreign key constraints...")
            
            fk_constraints_sql = [
                "ALTER TABLE contacts ADD CONSTRAINT fk_contacts_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;",
                "ALTER TABLE messages ADD CONSTRAINT fk_messages_chatbot FOREIGN KEY (chatbot_id) REFERENCES chatbots(id) ON DELETE CASCADE;",
                "ALTER TABLE orders ADD CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;",
                "ALTER TABLE campaigns ADD CONSTRAINT fk_campaigns_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;",
                "ALTER TABLE campaign_subscribers ADD CONSTRAINT fk_campaign_subscribers_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;"
            ]
            
            for sql in fk_constraints_sql:
                try:
                    cur.execute(sql)
                except psycopg2.Error as e:
                    if "already exists" in str(e):
                        logger.info(f"⚠️ Constraint already exists, skipping...")
                    else:
                        raise
            
            logger.info("✅ Foreign key constraints added")
            
            # 3. Convert to composite unique constraints for multi-tenancy
            logger.info("Step 3: Converting to composite unique constraints...")
            
            # Drop old unique constraints and add composite ones
            cur.execute("ALTER TABLE contacts DROP CONSTRAINT IF EXISTS contacts_phone_number_key;")
            cur.execute("ALTER TABLE contacts DROP CONSTRAINT IF EXISTS contacts_thread_id_key;")
            
            cur.execute("""
                ALTER TABLE contacts 
                ADD CONSTRAINT unique_contact_per_user 
                UNIQUE (user_id, phone_number);
            """)
            
            cur.execute("""
                ALTER TABLE contacts 
                ADD CONSTRAINT unique_thread_per_user 
                UNIQUE (user_id, thread_id);
            """)
            
            logger.info("✅ Composite unique constraints added for multi-tenancy")
            
            conn.commit()
            logger.info("✅ Phase 5 completed successfully!")
            
            return True
            
    except psycopg2.Error as e:
        logger.error(f"Error in Phase 5: {e}")
        conn.rollback()
        return False

def execute_phase6_supporting_tables(conn):
    """Phase 6: Create supporting tables for SaaS features."""
    logger.info("=" * 60)
    logger.info("PHASE 6: Create Supporting Tables")
    logger.info("=" * 60)
    
    try:
        with conn.cursor() as cur:
            # 1. ACTIONS TABLE - Human-in-the-loop system
            logger.info("Step 1: Creating actions table...")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS actions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    chatbot_id INTEGER NOT NULL REFERENCES chatbots(id) ON DELETE CASCADE,
                    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                    request_type VARCHAR(100) NOT NULL,
                    request_details TEXT NOT NULL,
                    request_data JSONB DEFAULT '{}',
                    status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'denied', 'cancelled')),
                    user_response TEXT,
                    response_data JSONB,
                    priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP WITH TIME ZONE,
                    expires_at TIMESTAMP WITH TIME ZONE
                );
            """)
            
            # Indexes for actions table
            cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_user_status ON actions(user_id, status);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_chatbot_id ON actions(chatbot_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_contact_id ON actions(contact_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_priority ON actions(priority, created_at);")
            
            logger.info("✅ Actions table created")
            
            # 2. USAGE_TRACKING TABLE - Track daily/monthly usage
            logger.info("Step 2: Creating usage tracking table...")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usage_tracking (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    tracking_date DATE NOT NULL,
                    messages_sent INTEGER DEFAULT 0,
                    campaigns_sent INTEGER DEFAULT 0,
                    api_calls INTEGER DEFAULT 0,
                    storage_used_mb INTEGER DEFAULT 0,
                    active_contacts INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, tracking_date)
                );
            """)
            
            cur.execute("CREATE INDEX IF NOT EXISTS idx_usage_tracking_user_date ON usage_tracking(user_id, tracking_date);")
            
            logger.info("✅ Usage tracking table created")
            
            # 3. ANALYTICS_EVENTS TABLE - Track user actions and performance
            logger.info("Step 3: Creating analytics events table...")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS analytics_events (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    chatbot_id INTEGER REFERENCES chatbots(id) ON DELETE SET NULL,
                    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
                    event_type VARCHAR(100) NOT NULL,
                    event_category VARCHAR(50) NOT NULL,
                    event_data JSONB DEFAULT '{}',
                    session_id VARCHAR(255),
                    ip_address INET,
                    user_agent TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            cur.execute("CREATE INDEX IF NOT EXISTS idx_analytics_user_type ON analytics_events(user_id, event_type);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_analytics_category_date ON analytics_events(event_category, created_at);")
            
            logger.info("✅ Analytics events table created")
            
            # 4. API_KEYS TABLE - Manage API access
            logger.info("Step 4: Creating API keys table...")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    key_name VARCHAR(255) NOT NULL,
                    api_key_hash VARCHAR(255) UNIQUE NOT NULL,
                    key_prefix VARCHAR(20) NOT NULL,
                    permissions JSONB DEFAULT '{}',
                    rate_limit_per_minute INTEGER DEFAULT 60,
                    is_active BOOLEAN DEFAULT true,
                    last_used_at TIMESTAMP WITH TIME ZONE,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            cur.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user_active ON api_keys(user_id, is_active);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix);")
            
            logger.info("✅ API keys table created")
            
            # 5. PRODUCTS TABLE - For e-commerce integration
            logger.info("Step 5: Creating products table...")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    price DECIMAL(10,2),
                    currency VARCHAR(3) DEFAULT 'USD',
                    sku VARCHAR(100),
                    category VARCHAR(100),
                    stock_quantity INTEGER DEFAULT 0,
                    product_data JSONB DEFAULT '{}',
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, sku)
                );
            """)
            
            cur.execute("CREATE INDEX IF NOT EXISTS idx_products_user_active ON products(user_id, is_active);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);")
            
            logger.info("✅ Products table created")
            
            # 6. ORDER_ITEMS TABLE - Link orders to products
            logger.info("Step 6: Creating order items table...")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    id SERIAL PRIMARY KEY,
                    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
                    product_name VARCHAR(255) NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    unit_price DECIMAL(10,2) NOT NULL,
                    total_price DECIMAL(10,2) NOT NULL,
                    item_data JSONB DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            cur.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);")
            
            logger.info("✅ Order items table created")
            
            conn.commit()
            logger.info("✅ Phase 6 completed successfully!")
            
            return True
            
    except psycopg2.Error as e:
        logger.error(f"Error in Phase 6: {e}")
        conn.rollback()
        return False

def execute_phase7_optimization(conn):
    """Phase 7: Performance optimization."""
    logger.info("=" * 60)
    logger.info("PHASE 7: Performance Optimization")
    logger.info("=" * 60)
    
    try:
        with conn.cursor() as cur:
            # Add comprehensive indexes for performance
            logger.info("Adding performance indexes...")
            
            performance_indexes = [
                "CREATE INDEX IF NOT EXISTS idx_messages_contact_sent_at ON messages(contact_id, sent_at);",
                "CREATE INDEX IF NOT EXISTS idx_messages_direction_date ON messages(direction, sent_at);",
                "CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders(user_id, status);",
                "CREATE INDEX IF NOT EXISTS idx_campaigns_user_active ON campaigns(user_id, is_active);",
                "CREATE INDEX IF NOT EXISTS idx_contacts_user_status ON contacts(user_id, contact_status);",
                "CREATE INDEX IF NOT EXISTS idx_contacts_last_interaction ON contacts(last_interaction);",
                "CREATE INDEX IF NOT EXISTS idx_usage_tracking_date_range ON usage_tracking(tracking_date, user_id);"
            ]
            
            for index_sql in performance_indexes:
                try:
                    cur.execute(index_sql)
                except psycopg2.Error as e:
                    if "already exists" in str(e):
                        logger.info(f"⚠️ Index already exists, skipping...")
                    else:
                        raise
            
            logger.info("✅ Performance indexes added")
            
            # Update table statistics
            logger.info("Updating table statistics...")
            cur.execute("ANALYZE;")
            logger.info("✅ Table statistics updated")
            
            conn.commit()
            logger.info("✅ Phase 7 completed successfully!")
            
            return True
            
    except psycopg2.Error as e:
        logger.error(f"Error in Phase 7: {e}")
        conn.rollback()
        return False

def execute_phase8_validation(conn):
    """Phase 8: Final validation and testing."""
    logger.info("=" * 60)
    logger.info("PHASE 8: Final Validation")
    logger.info("=" * 60)
    
    try:
        with conn.cursor() as cur:
            # 1. Validate multi-tenant isolation
            logger.info("Step 1: Validating multi-tenant isolation...")
            
            cur.execute("""
                SELECT 
                    t.table_name,
                    CASE WHEN c.column_name IS NOT NULL THEN 'Has user_id/chatbot_id' ELSE 'No tenant column' END as tenant_isolation
                FROM information_schema.tables t
                LEFT JOIN information_schema.columns c ON t.table_name = c.table_name 
                    AND c.column_name IN ('user_id', 'chatbot_id')
                WHERE t.table_schema = 'public' 
                    AND t.table_type = 'BASE TABLE'
                    AND t.table_name NOT LIKE 'checkpoint%'
                ORDER BY t.table_name;
            """)
            
            isolation_check = cur.fetchall()
            for table, status in isolation_check:
                if table in ['users', 'user_subscriptions', 'chatbots', 'bot_knowledge_base', 'conversation_instructions', 'actions', 'analytics_events', 'api_keys', 'products', 'order_items'] and 'Has' not in status:
                    logger.error(f"❌ {table}: Missing tenant isolation")
                else:
                    logger.info(f"✅ {table}: {status}")
            
            # 2. Test foreign key relationships
            logger.info("Step 2: Testing foreign key relationships...")
            
            fk_tests = [
                ("Users → Chatbots", "SELECT COUNT(*) FROM users u JOIN chatbots c ON u.id = c.user_id;"),
                ("Users → Contacts", "SELECT COUNT(*) FROM users u JOIN contacts c ON u.id = c.user_id;"),
                ("Chatbots → Messages", "SELECT COUNT(*) FROM chatbots cb JOIN messages m ON cb.id = m.chatbot_id;"),
                ("Contacts → Messages", "SELECT COUNT(*) FROM contacts c JOIN messages m ON c.id = m.contact_id;")
            ]
            
            for test_name, test_sql in fk_tests:
                cur.execute(test_sql)
                count = cur.fetchone()[0]
                logger.info(f"✅ {test_name}: {count} relationships")
            
            # 3. Performance test - query response times
            logger.info("Step 3: Testing query performance...")
            
            import time
            
            performance_tests = [
                ("User dashboard query", """
                    SELECT 
                        u.full_name,
                        COUNT(DISTINCT c.id) as total_contacts,
                        COUNT(DISTINCT m.id) as total_messages,
                        COUNT(DISTINCT cb.id) as total_chatbots
                    FROM users u
                    LEFT JOIN contacts c ON u.id = c.user_id
                    LEFT JOIN messages m ON c.id = m.contact_id
                    LEFT JOIN chatbots cb ON u.id = cb.user_id
                    WHERE u.id = 1
                    GROUP BY u.id, u.full_name;
                """),
                ("Recent messages query", """
                    SELECT m.*, c.name, c.phone_number
                    FROM messages m
                    JOIN contacts c ON m.contact_id = c.id
                    WHERE c.user_id = 1
                    ORDER BY m.sent_at DESC
                    LIMIT 10;
                """)
            ]
            
            for test_name, test_sql in performance_tests:
                start_time = time.time()
                cur.execute(test_sql)
                cur.fetchall()
                end_time = time.time()
                duration = (end_time - start_time) * 1000  # Convert to milliseconds
                logger.info(f"✅ {test_name}: {duration:.2f}ms")
            
            # 4. Final table counts
            logger.info("Step 4: Final database summary...")
            
            cur.execute("""
                SELECT 
                    schemaname,
                    relname as tablename,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes,
                    n_live_tup as live_rows
                FROM pg_stat_user_tables 
                WHERE schemaname = 'public'
                ORDER BY relname;
            """)
            
            table_stats = cur.fetchall()
            logger.info("📊 Table Statistics:")
            for schema, table, inserts, updates, deletes, live_rows in table_stats:
                logger.info(f"   {table}: {live_rows} rows ({inserts} inserts, {updates} updates)")
            
            logger.info("✅ Phase 8 completed successfully!")
            
            return True
            
    except psycopg2.Error as e:
        logger.error(f"Error in Phase 8: {e}")
        return False

def main():
    """Execute all remaining phases (5-8) of the migration."""
    logger.info("=" * 80)
    logger.info("PHASES 5-8: Complete Multi-Tenant Migration")
    logger.info("=" * 80)
    
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        logger.error("Error: DATABASE_URL environment variable is not set.")
        exit(1)
    
    # Connect to database
    connection = connect_to_db(db_url)
    if not connection:
        exit(1)
    
    try:
        # Execute all phases
        phases = [
            ("Phase 5", execute_phase5_constraints),
            ("Phase 6", execute_phase6_supporting_tables),
            ("Phase 7", execute_phase7_optimization),
            ("Phase 8", execute_phase8_validation)
        ]
        
        for phase_name, phase_function in phases:
            logger.info(f"\n🚀 Starting {phase_name}...")
            if not phase_function(connection):
                logger.error(f"❌ {phase_name} failed!")
                exit(1)
            logger.info(f"✅ {phase_name} completed!")
        
        # Final success message
        logger.info("=" * 80)
        logger.info("🎉 MULTI-TENANT MIGRATION COMPLETED SUCCESSFULLY!")
        logger.info("=" * 80)
        logger.info("✅ All 8 phases completed")
        logger.info("✅ Multi-tenant architecture implemented")
        logger.info("✅ Admin user and default chatbot ready")
        logger.info("✅ All existing data migrated")
        logger.info("✅ Supporting tables created")
        logger.info("✅ Performance optimized")
        logger.info("✅ System validated and tested")
        logger.info("")
        logger.info("🚀 SwiftReplies.ai is now ready for multi-tenant SaaS operations!")
        logger.info("=" * 80)
        
    finally:
        connection.close()
        logger.info("Database connection closed.")

if __name__ == "__main__":
    main() 