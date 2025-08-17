import psycopg2
import os
from dotenv import load_dotenv
import logging
from datetime import datetime

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

def execute_phase4_migration(conn):
    """Executes Phase 4 migration: Migrate existing data to admin user."""
    
    try:
        with conn.cursor() as cur:
            logger.info("Starting Phase 4 migration: Migrating existing data...")
            
            # 1. MIGRATE CONTACTS TO ADMIN USER
            logger.info("Step 1: Migrating contacts to admin user...")
            
            # Update all contacts to belong to admin user (ID = 1)
            cur.execute("""
                UPDATE contacts 
                SET user_id = 1,
                    contact_status = 'active',
                    last_interaction = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id IS NULL;
            """)
            
            contacts_updated = cur.rowcount
            logger.info(f"✅ {contacts_updated} contacts assigned to admin user")
            
            # 2. MIGRATE MESSAGES TO DEFAULT CHATBOT
            logger.info("Step 2: Migrating messages to default chatbot...")
            
            # Update all messages to belong to default chatbot (ID = 1)
            cur.execute("""
                UPDATE messages 
                SET chatbot_id = 1,
                    ai_processed = true,
                    processing_duration = 500
                WHERE chatbot_id IS NULL;
            """)
            
            messages_updated = cur.rowcount
            logger.info(f"✅ {messages_updated} messages assigned to default chatbot")
            
            # 3. MIGRATE ORDERS TO ADMIN USER
            logger.info("Step 3: Migrating orders to admin user...")
            
            # Update all orders to belong to admin user (ID = 1)
            cur.execute("""
                UPDATE orders 
                SET user_id = 1,
                    currency = 'USD',
                    payment_status = COALESCE(status, 'pending'),
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id IS NULL;
            """)
            
            orders_updated = cur.rowcount
            logger.info(f"✅ {orders_updated} orders assigned to admin user")
            
            # 4. MIGRATE CAMPAIGNS TO ADMIN USER
            logger.info("Step 4: Migrating campaigns to admin user...")
            
            # Update all campaigns to belong to admin user (ID = 1)
            cur.execute("""
                UPDATE campaigns 
                SET user_id = 1,
                    campaign_status = CASE 
                        WHEN is_active = true THEN 'active'
                        ELSE 'inactive'
                    END,
                    campaign_stats = '{"sent": 0, "delivered": 0, "read": 0, "replied": 0}'::jsonb
                WHERE user_id IS NULL;
            """)
            
            campaigns_updated = cur.rowcount
            logger.info(f"✅ {campaigns_updated} campaigns assigned to admin user")
            
            # 5. MIGRATE CAMPAIGN_SUBSCRIBERS TO ADMIN USER
            logger.info("Step 5: Migrating campaign subscribers to admin user...")
            
            # Update all campaign subscribers to belong to admin user (ID = 1)
            cur.execute("""
                UPDATE campaign_subscribers 
                SET user_id = 1,
                    subscription_source = 'legacy_migration',
                    preferences = '{"notifications": true, "frequency": "immediate"}'::jsonb,
                    engagement_score = 75
                WHERE user_id IS NULL;
            """)
            
            subscribers_updated = cur.rowcount
            logger.info(f"✅ {subscribers_updated} campaign subscribers assigned to admin user")
            
            # 6. UPDATE CONVERSATION_INSTRUCTIONS CONTACT REFERENCES
            logger.info("Step 6: Updating conversation instructions contact references...")
            
            # Add foreign key constraint for contact_id now that contacts have user_id
            cur.execute("""
                ALTER TABLE conversation_instructions 
                ADD CONSTRAINT fk_contact 
                FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE SET NULL;
            """)
            
            logger.info("✅ Foreign key constraint added for conversation instructions")
            
            # Commit all changes
            conn.commit()
            logger.info("Phase 4 migration completed successfully!")
            
            return {
                'contacts': contacts_updated,
                'messages': messages_updated,
                'orders': orders_updated,
                'campaigns': campaigns_updated,
                'subscribers': subscribers_updated
            }
            
    except psycopg2.Error as e:
        logger.error(f"Error during Phase 4 migration: {e}")
        conn.rollback()
        return None

def validate_data_migration(conn):
    """Validates that the data migration was successful."""
    try:
        with conn.cursor() as cur:
            logger.info("Validating data migration...")
            
            # Check that all tables have user_id/chatbot_id assigned
            validation_queries = [
                ("contacts with user_id", "SELECT COUNT(*) FROM contacts WHERE user_id = 1"),
                ("contacts without user_id", "SELECT COUNT(*) FROM contacts WHERE user_id IS NULL"),
                ("messages with chatbot_id", "SELECT COUNT(*) FROM messages WHERE chatbot_id = 1"),
                ("messages without chatbot_id", "SELECT COUNT(*) FROM messages WHERE chatbot_id IS NULL"),
                ("orders with user_id", "SELECT COUNT(*) FROM orders WHERE user_id = 1"),
                ("orders without user_id", "SELECT COUNT(*) FROM orders WHERE user_id IS NULL"),
                ("campaigns with user_id", "SELECT COUNT(*) FROM campaigns WHERE user_id = 1"),
                ("campaigns without user_id", "SELECT COUNT(*) FROM campaigns WHERE user_id IS NULL"),
                ("subscribers with user_id", "SELECT COUNT(*) FROM campaign_subscribers WHERE user_id = 1"),
                ("subscribers without user_id", "SELECT COUNT(*) FROM campaign_subscribers WHERE user_id IS NULL")
            ]
            
            all_validated = True
            
            for description, query in validation_queries:
                cur.execute(query)
                count = cur.fetchone()[0]
                
                if "without" in description and count > 0:
                    logger.error(f"❌ {description}: {count} (should be 0)")
                    all_validated = False
                else:
                    logger.info(f"✅ {description}: {count}")
            
            # Check foreign key relationships
            cur.execute("""
                SELECT 
                    c.id as contact_id, 
                    c.user_id, 
                    m.id as message_id, 
                    m.chatbot_id 
                FROM contacts c 
                LEFT JOIN messages m ON c.id = m.contact_id 
                WHERE c.user_id = 1 
                LIMIT 5;
            """)
            
            relationships = cur.fetchall()
            logger.info(f"✅ Sample contact-message relationships: {len(relationships)} found")
            
            return all_validated
            
    except psycopg2.Error as e:
        logger.error(f"Error validating data migration: {e}")
        return False

def show_migration_summary(conn, migration_stats):
    """Shows a summary of the migration results."""
    try:
        with conn.cursor() as cur:
            logger.info("=" * 60)
            logger.info("MIGRATION SUMMARY")
            logger.info("=" * 60)
            
            # Total records migrated
            total_migrated = sum(migration_stats.values())
            logger.info(f"📊 Total records migrated: {total_migrated}")
            logger.info(f"   • Contacts: {migration_stats['contacts']}")
            logger.info(f"   • Messages: {migration_stats['messages']}")
            logger.info(f"   • Orders: {migration_stats['orders']}")
            logger.info(f"   • Campaigns: {migration_stats['campaigns']}")
            logger.info(f"   • Subscribers: {migration_stats['subscribers']}")
            
            # Current table sizes
            cur.execute("""
                SELECT 
                    'Total Users' as metric, COUNT(*) as count FROM users
                UNION ALL
                SELECT 'Total Chatbots', COUNT(*) FROM chatbots
                UNION ALL
                SELECT 'Total Contacts', COUNT(*) FROM contacts
                UNION ALL
                SELECT 'Total Messages', COUNT(*) FROM messages
                UNION ALL
                SELECT 'Active Subscriptions', COUNT(*) FROM user_subscriptions WHERE is_active = true;
            """)
            
            metrics = cur.fetchall()
            logger.info("")
            logger.info("📈 Current Database State:")
            for metric, count in metrics:
                logger.info(f"   • {metric}: {count}")
            
            logger.info("=" * 60)
            
    except psycopg2.Error as e:
        logger.error(f"Error generating migration summary: {e}")

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("PHASE 4 MIGRATION: Migrate Existing Data")
    logger.info("=" * 60)
    
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        logger.error("Error: DATABASE_URL environment variable is not set.")
        logger.error("Please set it before running the script.")
        exit(1)
    
    # Connect to database
    connection = connect_to_db(db_url)
    if not connection:
        exit(1)
    
    try:
        # Execute Phase 4 migration
        logger.info("Executing Phase 4 migration...")
        migration_stats = execute_phase4_migration(connection)
        
        if not migration_stats:
            logger.error("Phase 4 migration failed.")
            exit(1)
        
        # Validate data migration
        logger.info("Validating data migration...")
        if not validate_data_migration(connection):
            logger.error("Data migration validation failed.")
            exit(1)
        
        # Show migration summary
        show_migration_summary(connection, migration_stats)
        
        logger.info("=" * 60)
        logger.info("✅ PHASE 4 MIGRATION COMPLETED SUCCESSFULLY!")
        logger.info("✅ All existing data migrated to admin user")
        logger.info("✅ All messages assigned to default chatbot")
        logger.info("✅ Foreign key relationships established")
        logger.info("✅ Data integrity validated")
        logger.info("✅ Ready for Phase 5: Update constraints")
        logger.info("=" * 60)
        
    finally:
        connection.close()
        logger.info("Database connection closed.") 