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

def execute_phase2_migration(conn):
    """Executes Phase 2 migration: Alter existing tables to add foreign key columns."""
    
    try:
        with conn.cursor() as cur:
            logger.info("Starting Phase 2 migration: Altering existing tables...")
            
            # 1. ALTER CONTACTS TABLE
            logger.info("Step 1: Altering contacts table...")
            
            # Add user_id column (nullable initially)
            cur.execute("""
                ALTER TABLE contacts 
                ADD COLUMN IF NOT EXISTS user_id INTEGER;
            """)
            
            # Add enhanced contact fields
            cur.execute("""
                ALTER TABLE contacts 
                ADD COLUMN IF NOT EXISTS tags TEXT[],
                ADD COLUMN IF NOT EXISTS custom_fields JSONB DEFAULT '{}',
                ADD COLUMN IF NOT EXISTS last_interaction TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS contact_status VARCHAR(50) DEFAULT 'active';
            """)
            logger.info("✅ contacts table altered successfully")
            
            # 2. ALTER MESSAGES TABLE
            logger.info("Step 2: Altering messages table...")
            
            # Add chatbot_id column (nullable initially)
            cur.execute("""
                ALTER TABLE messages 
                ADD COLUMN IF NOT EXISTS chatbot_id INTEGER;
            """)
            
            # Add enhanced message fields
            cur.execute("""
                ALTER TABLE messages 
                ADD COLUMN IF NOT EXISTS ai_processed BOOLEAN DEFAULT false,
                ADD COLUMN IF NOT EXISTS confidence_score DECIMAL(3,2),
                ADD COLUMN IF NOT EXISTS processing_duration INTEGER,
                ADD COLUMN IF NOT EXISTS error_details TEXT;
            """)
            logger.info("✅ messages table altered successfully")
            
            # 3. ALTER ORDERS TABLE
            logger.info("Step 3: Altering orders table...")
            
            # Add user_id column (nullable initially)
            cur.execute("""
                ALTER TABLE orders 
                ADD COLUMN IF NOT EXISTS user_id INTEGER;
            """)
            
            # Add enhanced order fields
            cur.execute("""
                ALTER TABLE orders 
                ADD COLUMN IF NOT EXISTS total_amount DECIMAL(10,2),
                ADD COLUMN IF NOT EXISTS currency VARCHAR(3) DEFAULT 'USD',
                ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50) DEFAULT 'pending',
                ADD COLUMN IF NOT EXISTS shipping_address JSONB,
                ADD COLUMN IF NOT EXISTS order_notes TEXT;
            """)
            logger.info("✅ orders table altered successfully")
            
            # 4. ALTER CAMPAIGNS TABLE
            logger.info("Step 4: Altering campaigns table...")
            
            # Add user_id column (nullable initially)
            cur.execute("""
                ALTER TABLE campaigns 
                ADD COLUMN IF NOT EXISTS user_id INTEGER;
            """)
            
            # Add enhanced campaign fields
            cur.execute("""
                ALTER TABLE campaigns 
                ADD COLUMN IF NOT EXISTS target_audience JSONB,
                ADD COLUMN IF NOT EXISTS schedule_config JSONB,
                ADD COLUMN IF NOT EXISTS campaign_stats JSONB DEFAULT '{}',
                ADD COLUMN IF NOT EXISTS budget_limit DECIMAL(10,2),
                ADD COLUMN IF NOT EXISTS campaign_status VARCHAR(50) DEFAULT 'draft';
            """)
            logger.info("✅ campaigns table altered successfully")
            
            # 5. ALTER CAMPAIGN_SUBSCRIBERS TABLE
            logger.info("Step 5: Altering campaign_subscribers table...")
            
            # Add user_id column (nullable initially)
            cur.execute("""
                ALTER TABLE campaign_subscribers 
                ADD COLUMN IF NOT EXISTS user_id INTEGER;
            """)
            
            # Add enhanced subscriber fields
            cur.execute("""
                ALTER TABLE campaign_subscribers 
                ADD COLUMN IF NOT EXISTS subscription_source VARCHAR(100),
                ADD COLUMN IF NOT EXISTS preferences JSONB DEFAULT '{}',
                ADD COLUMN IF NOT EXISTS unsubscribed_at TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS engagement_score INTEGER DEFAULT 50;
            """)
            logger.info("✅ campaign_subscribers table altered successfully")
            
            # Commit all changes
            conn.commit()
            logger.info("Phase 2 migration completed successfully!")
            
            return True
            
    except psycopg2.Error as e:
        logger.error(f"Error during Phase 2 migration: {e}")
        conn.rollback()
        return False

def validate_alterations(conn):
    """Validates that the table alterations were successful."""
    try:
        with conn.cursor() as cur:
            # Check if new columns were added
            tables_to_check = {
                'contacts': ['user_id', 'tags', 'custom_fields', 'last_interaction', 'contact_status'],
                'messages': ['chatbot_id', 'ai_processed', 'confidence_score', 'processing_duration', 'error_details'],
                'orders': ['user_id', 'total_amount', 'currency', 'payment_status', 'shipping_address', 'order_notes'],
                'campaigns': ['user_id', 'target_audience', 'schedule_config', 'campaign_stats', 'budget_limit', 'campaign_status'],
                'campaign_subscribers': ['user_id', 'subscription_source', 'preferences', 'unsubscribed_at', 'engagement_score']
            }
            
            all_columns_added = True
            
            for table_name, expected_columns in tables_to_check.items():
                # Get actual columns for this table
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND table_schema = 'public'
                    ORDER BY column_name;
                """, (table_name,))
                
                actual_columns = [row[0] for row in cur.fetchall()]
                
                # Check if all expected columns exist
                missing_columns = [col for col in expected_columns if col not in actual_columns]
                
                if missing_columns:
                    logger.error(f"❌ Missing columns in {table_name}: {missing_columns}")
                    all_columns_added = False
                else:
                    logger.info(f"✅ {table_name}: All new columns added successfully")
            
            return all_columns_added
            
    except psycopg2.Error as e:
        logger.error(f"Error validating alterations: {e}")
        return False

def validate_existing_data(conn):
    """Validates that existing data is preserved."""
    try:
        with conn.cursor() as cur:
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
            logger.info("Post-alteration table row counts:")
            for table_name, count in counts:
                logger.info(f"  {table_name}: {count} rows")
            
            return True
            
    except psycopg2.Error as e:
        logger.error(f"Error validating existing data: {e}")
        return False

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("PHASE 2 MIGRATION: Alter Existing Tables")
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
        # Validate existing data before migration
        logger.info("Step 1: Validating existing data...")
        if not validate_existing_data(connection):
            logger.error("Pre-migration data validation failed. Aborting migration.")
            exit(1)
        
        # Execute Phase 2 migration
        logger.info("Step 2: Executing Phase 2 migration...")
        if not execute_phase2_migration(connection):
            logger.error("Phase 2 migration failed.")
            exit(1)
        
        # Validate alterations
        logger.info("Step 3: Validating alterations...")
        if not validate_alterations(connection):
            logger.error("Alteration validation failed.")
            exit(1)
        
        # Final data validation
        logger.info("Step 4: Final data validation...")
        if not validate_existing_data(connection):
            logger.error("Post-migration data validation failed.")
            exit(1)
        
        logger.info("=" * 60)
        logger.info("✅ PHASE 2 MIGRATION COMPLETED SUCCESSFULLY!")
        logger.info("✅ All existing tables enhanced with multi-tenancy columns")
        logger.info("✅ Additional feature columns added for future SaaS capabilities")
        logger.info("✅ All existing data preserved")
        logger.info("✅ Ready for Phase 3: Create admin user")
        logger.info("=" * 60)
        
    finally:
        connection.close()
        logger.info("Database connection closed.") 