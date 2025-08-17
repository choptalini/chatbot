import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv
import logging
import hashlib
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

def hash_password(password):
    """Simple password hashing (use proper hashing in production)."""
    return hashlib.sha256(password.encode()).hexdigest()

def execute_phase3_migration(conn):
    """Executes Phase 3 migration: Create admin user, subscription, and default chatbot."""
    
    try:
        with conn.cursor() as cur:
            logger.info("Starting Phase 3 migration: Creating admin user setup...")
            
            # 1. CREATE ADMIN USER (ID = 1)
            logger.info("Step 1: Creating admin user...")
            
            admin_email = "admin@swiftreplies.ai"
            admin_password = hash_password("SwiftReplies2025!")  # Change this in production
            
            cur.execute("""
                INSERT INTO users (
                    id, email, password_hash, full_name, company_name, 
                    phone, is_active, created_at, updated_at
                ) VALUES (
                    1, %s, %s, 'System Administrator', 'SwiftReplies AI', 
                    '+1234567890', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    full_name = EXCLUDED.full_name,
                    company_name = EXCLUDED.company_name,
                    updated_at = CURRENT_TIMESTAMP;
            """, (admin_email, admin_password))
            
            # Reset sequence to ensure next user gets ID > 1
            cur.execute("SELECT setval('users_id_seq', 1, true);")
            
            logger.info("✅ Admin user created with ID = 1")
            
            # 2. CREATE UNLIMITED SUBSCRIPTION FOR ADMIN
            logger.info("Step 2: Creating unlimited subscription for admin...")
            
            unlimited_config = {
                "features": {
                    "multi_chatbot": True,
                    "analytics_dashboard": True,
                    "api_access": True,
                    "live_chat_takeover": True,
                    "actions_center": True,
                    "campaign_management": True,
                    "contact_management": True,
                    "custom_integrations": True,
                    "priority_support": True,
                    "white_label": True
                },
                "limits": {
                    "chatbots": "unlimited",
                    "contacts": "unlimited",
                    "api_calls_per_day": "unlimited",
                    "storage_gb": "unlimited"
                },
                "permissions": {
                    "admin_access": True,
                    "user_management": True,
                    "system_settings": True,
                    "billing_access": True,
                    "analytics_export": True
                }
            }
            
            cur.execute("""
                INSERT INTO user_subscriptions (
                    user_id, subscription_name, subscription_config,
                    daily_message_limit, monthly_message_limit,
                    daily_campaign_limit, monthly_campaign_limit,
                    billing_amount, billing_currency, billing_cycle,
                    contract_start_date, contract_end_date, auto_renew,
                    is_active, created_at, updated_at
                ) VALUES (
                    1, 'Admin Unlimited Plan', %s,
                    999999999, 999999999,
                    999999999, 999999999,
                    0.00, 'USD', 'lifetime',
                    %s, null, false,
                    true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON CONFLICT DO NOTHING;
            """, (json.dumps(unlimited_config), date.today()))
            
            logger.info("✅ Unlimited subscription created for admin")
            
            # 3. CREATE DEFAULT CHATBOT (ID = 1)
            logger.info("Step 3: Creating default chatbot...")
            
            default_instructions = """
You are SwiftReplies AI, a helpful WhatsApp business assistant. Your primary goals are:

1. **Customer Support**: Answer questions professionally and helpfully
2. **Sales Assistance**: Help customers find products and complete purchases
3. **Lead Qualification**: Gather contact information from potential customers
4. **Appointment Booking**: Help schedule meetings or consultations

**Key Guidelines:**
- Always be polite, professional, and helpful
- Keep responses concise but informative
- Ask clarifying questions when needed
- Escalate complex issues to human agents using the Actions system
- Use emojis sparingly and appropriately
- Always end conversations with next steps or follow-up information

**Current Business Hours**: 9 AM - 6 PM (Monday - Friday)
**Response Time Goal**: Under 30 seconds during business hours

If you cannot handle a request or need human intervention, use the Actions system to request assistance.
            """
            
            cur.execute("""
                INSERT INTO chatbots (
                    id, user_id, name, whatsapp_phone_number, 
                    general_instructions, is_active, bot_status,
                    created_at, updated_at
                ) VALUES (
                    1, 1, 'Default SwiftReplies Bot', null,
                    %s, true, 'active',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    general_instructions = EXCLUDED.general_instructions,
                    updated_at = CURRENT_TIMESTAMP;
            """, (default_instructions,))
            
            # Reset sequence to ensure next chatbot gets ID > 1
            cur.execute("SELECT setval('chatbots_id_seq', 1, true);")
            
            logger.info("✅ Default chatbot created with ID = 1")
            
            # 4. CREATE SAMPLE KNOWLEDGE BASE ENTRIES
            logger.info("Step 4: Creating sample knowledge base entries...")
            
            sample_kb_entries = [
                ("General", "What are your business hours?", "Our business hours are Monday through Friday, 9 AM to 6 PM. We're closed on weekends and major holidays."),
                ("General", "How can I contact support?", "You can contact our support team right here via WhatsApp, or email us at support@swiftreplies.ai. We typically respond within 30 minutes during business hours."),
                ("Pricing", "How much does SwiftReplies cost?", "We offer custom pricing plans tailored to your business needs. Contact us for a personalized quote based on your message volume and required features."),
                ("Features", "What features does SwiftReplies offer?", "SwiftReplies offers AI-powered conversations, live chat takeover, analytics dashboard, campaign management, contact management, API access, and much more!"),
                ("Technical", "How do I integrate SwiftReplies with my system?", "We provide REST APIs and webhooks for easy integration. Our technical team can help you set up custom integrations. Would you like to speak with our technical specialist?")
            ]
            
            for category, question, answer in sample_kb_entries:
                cur.execute("""
                    INSERT INTO bot_knowledge_base (
                        user_id, chatbot_id, category, question, answer, 
                        is_active, created_at, updated_at
                    ) VALUES (
                        1, 1, %s, %s, %s,
                        true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    ON CONFLICT DO NOTHING;
                """, (category, question, answer))
            
            logger.info("✅ Sample knowledge base entries created")
            
            # Commit all changes
            conn.commit()
            logger.info("Phase 3 migration completed successfully!")
            
            return True
            
    except psycopg2.Error as e:
        logger.error(f"Error during Phase 3 migration: {e}")
        conn.rollback()
        return False

def validate_admin_setup(conn):
    """Validates that the admin setup was successful."""
    try:
        with conn.cursor() as cur:
            # Check admin user
            cur.execute("SELECT id, email, full_name, is_active FROM users WHERE id = 1;")
            admin_user = cur.fetchone()
            
            if admin_user:
                logger.info(f"✅ Admin user: ID={admin_user[0]}, Email={admin_user[1]}, Name={admin_user[2]}, Active={admin_user[3]}")
            else:
                logger.error("❌ Admin user not found")
                return False
            
            # Check admin subscription
            cur.execute("""
                SELECT subscription_name, daily_message_limit, monthly_message_limit, is_active 
                FROM user_subscriptions WHERE user_id = 1;
            """)
            admin_subscription = cur.fetchone()
            
            if admin_subscription:
                logger.info(f"✅ Admin subscription: {admin_subscription[0]}, Daily: {admin_subscription[1]}, Monthly: {admin_subscription[2]}, Active: {admin_subscription[3]}")
            else:
                logger.error("❌ Admin subscription not found")
                return False
            
            # Check default chatbot
            cur.execute("SELECT id, name, is_active, bot_status FROM chatbots WHERE id = 1;")
            default_bot = cur.fetchone()
            
            if default_bot:
                logger.info(f"✅ Default chatbot: ID={default_bot[0]}, Name={default_bot[1]}, Active={default_bot[2]}, Status={default_bot[3]}")
            else:
                logger.error("❌ Default chatbot not found")
                return False
            
            # Check knowledge base entries
            cur.execute("SELECT COUNT(*) FROM bot_knowledge_base WHERE user_id = 1 AND chatbot_id = 1;")
            kb_count = cur.fetchone()[0]
            logger.info(f"✅ Knowledge base entries: {kb_count} entries created")
            
            return True
            
    except psycopg2.Error as e:
        logger.error(f"Error validating admin setup: {e}")
        return False

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("PHASE 3 MIGRATION: Create Admin User Setup")
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
        # Execute Phase 3 migration
        logger.info("Executing Phase 3 migration...")
        if not execute_phase3_migration(connection):
            logger.error("Phase 3 migration failed.")
            exit(1)
        
        # Validate admin setup
        logger.info("Validating admin setup...")
        if not validate_admin_setup(connection):
            logger.error("Admin setup validation failed.")
            exit(1)
        
        logger.info("=" * 60)
        logger.info("✅ PHASE 3 MIGRATION COMPLETED SUCCESSFULLY!")
        logger.info("✅ Admin user created (ID: 1)")
        logger.info("✅ Unlimited subscription plan activated")
        logger.info("✅ Default chatbot ready (ID: 1)")
        logger.info("✅ Sample knowledge base populated")
        logger.info("✅ Ready for Phase 4: Data migration")
        logger.info("=" * 60)
        logger.info("")
        logger.info("🔐 ADMIN CREDENTIALS:")
        logger.info("   Email: admin@swiftreplies.ai")
        logger.info("   Password: SwiftReplies2025!")
        logger.info("   (Change password immediately in production)")
        logger.info("=" * 60)
        
    finally:
        connection.close()
        logger.info("Database connection closed.") 