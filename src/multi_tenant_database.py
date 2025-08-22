"""
Multi-Tenant Database Module for SwiftReplies.ai
Handles all database operations with multi-tenant support
"""

import psycopg2
import psycopg2.extras
import uuid
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import os
from dotenv import load_dotenv
import aiopg
import json


# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Import configuration
from .multi_tenant_config import config

# Constants for the admin user (fallback)
ADMIN_USER_ID = config.ADMIN_USER_ID
DEFAULT_CHATBOT_ID = config.DEFAULT_CHATBOT_ID

class MultiTenantDB:
    """Multi-tenant database operations manager."""
    
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable is not set")
    
    def connect_to_db(self):
        """Establishes a connection to the PostgreSQL database."""
        try:
            conn = psycopg2.connect(self.db_url)
            return conn
        except psycopg2.OperationalError as e:
            logger.error(f"Error connecting to the database: {e}")
            return None
    
    def get_user_by_phone_number(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Get user and chatbot info by phone number mapping.
        Uses configuration-based mapping during migration period.
        """
        return config.get_user_mapping(phone_number)
    
    def get_or_create_contact(
        self, 
        phone_number: str, 
        user_id: Optional[int] = None, 
        name: Optional[str] = None
    ) -> Tuple[Optional[int], Optional[str]]:
        """
        Retrieves a contact by phone number and user_id or creates a new one.
        Returns (contact_id, thread_id) or (None, None) on error.
        """
        if user_id is None:
            # Get user info from phone number mapping
            user_info = self.get_user_by_phone_number(phone_number)
            user_id = user_info['user_id']
        
        conn = self.connect_to_db()
        if not conn:
            return None, None

        try:
            with conn.cursor() as cur:
                # Check if contact exists for this user
                cur.execute(
                    "SELECT id, thread_id FROM contacts WHERE phone_number = %s AND user_id = %s", 
                    (phone_number, user_id)
                )
                contact = cur.fetchone()

                if contact:
                    contact_id, thread_id = contact
                    logger.info(f"Found existing contact: {contact_id} for user {user_id}")
                    # One-time backfill: if name is missing and a non-empty name is provided, update it in-place
                    if name and isinstance(name, str):
                        try:
                            cur.execute(
                                """
                                UPDATE contacts
                                SET name = COALESCE(NULLIF(name, ''), %s), updated_at = CURRENT_TIMESTAMP
                                WHERE id = %s AND (name IS NULL OR name = '')
                                """,
                                (name.strip(), contact_id)
                            )
                            if cur.rowcount:
                                conn.commit()
                                logger.info(f"Backfilled name for contact {contact_id}")
                        except psycopg2.Error:
                            conn.rollback()
                    return contact_id, thread_id
                else:
                    # Create new contact with new thread_id
                    new_thread_id = str(uuid.uuid4())
                    cur.execute(
                        """
                        INSERT INTO contacts (phone_number, user_id, name, thread_id, contact_status, last_interaction) 
                        VALUES (%s, %s, %s, %s, 'active', CURRENT_TIMESTAMP) 
                        RETURNING id
                        """,
                        (phone_number, user_id, name, new_thread_id)
                    )
                    contact_id = cur.fetchone()[0]
                    conn.commit()
                    logger.info(f"Created new contact: {contact_id} for user {user_id}")
                    return contact_id, new_thread_id
                    
        except psycopg2.Error as e:
            logger.error(f"Database error in get_or_create_contact: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
        
        return None, None

    def log_message(
        self, 
        contact_id: int, 
        message_id: str, 
        direction: str, 
        message_type: str, 
        chatbot_id: Optional[int] = None,
        content_text: Optional[str] = None, 
        content_url: Optional[str] = None, 
        status: str = 'delivered',
        metadata: Optional[Dict[str, Any]] = None,
        ai_processed: bool = False,
        confidence_score: Optional[float] = None,
        processing_duration: Optional[int] = None
    ) -> bool:
        """
        Logs a message to the messages table with multi-tenant support.
        Returns True on success, False on failure.
        """
        if chatbot_id is None:
            chatbot_id = DEFAULT_CHATBOT_ID
        
        conn = self.connect_to_db()
        if not conn:
            return False

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO messages (
                        contact_id, message_id, direction, message_type, 
                        content_text, content_url, status, sent_at, metadata,
                        chatbot_id, ai_processed, confidence_score, processing_duration
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s)
                    """,
                    (
                        contact_id, message_id, direction, message_type,
                        content_text, content_url, status, 
                        psycopg2.extras.Json(metadata) if metadata else None,
                        chatbot_id, ai_processed, confidence_score, processing_duration
                    )
                )
                conn.commit()
                logger.info(f"Message logged: {message_id} for contact {contact_id}")
                return True
                
        except psycopg2.Error as e:
            logger.error(f"Database error in log_message: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
        
        return False

    def update_contact_interaction(self, contact_id: int) -> bool:
        """Update the last interaction timestamp for a contact."""
        conn = self.connect_to_db()
        if not conn:
            return False

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE contacts SET last_interaction = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (contact_id,)
                )
                conn.commit()
                return True
        except psycopg2.Error as e:
            logger.error(f"Database error in update_contact_interaction: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
        
        return False

    def is_conversation_paused(self, contact_id: int) -> bool:
        """Check if a conversation is currently paused."""
        conn = self.connect_to_db()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT conversation_paused FROM contacts WHERE id = %s",
                    (contact_id,)
                )
                result = cur.fetchone()
                return result[0] if result else False
        except psycopg2.Error as e:
            logger.error(f"Database error in is_conversation_paused: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def update_message_status(self, message_id: int, status: str, whatsapp_message_id: str = None, error_details: str = None) -> bool:
        """Update the status of a message after sending to WhatsApp."""
        conn = self.connect_to_db()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cur:
                # Build dynamic update query based on provided parameters (removed updated_at since column doesn't exist)
                update_fields = ["status = %s"]
                params = [status]
                
                if whatsapp_message_id:
                    update_fields.append("message_id = %s")
                    params.append(whatsapp_message_id)
                
                if error_details:
                    # Append error details to content_text
                    update_fields.append("content_text = COALESCE(content_text, '') || ' [Error: ' || %s || ']'")
                    params.append(error_details)
                
                params.append(message_id)
                
                query = f"""
                    UPDATE messages 
                    SET {', '.join(update_fields)}
                    WHERE id = %s
                """
                
                cur.execute(query, params)
                conn.commit()
                
                if cur.rowcount > 0:
                    logger.info(f"Updated message {message_id} status to {status}")
                    return True
                else:
                    logger.warning(f"No message found with ID {message_id}")
                    return False
                    
        except psycopg2.Error as e:
            logger.error(f"Database error in update_message_status: {e}")
            conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def create_order(
        self, 
        contact_id: int, 
        user_id: int,
        order_details: Dict[str, Any], 
        message_id: Optional[int] = None,
        total_amount: Optional[float] = None,
        currency: str = 'USD',
        status: str = 'pending'
    ) -> Optional[int]:
        """
        Creates a new order with multi-tenant support.
        Returns order_id on success, None on failure.
        """
        conn = self.connect_to_db()
        if not conn:
            return None

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO orders (
                        contact_id, user_id, message_id, order_details, 
                        status, total_amount, currency, payment_status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        contact_id, user_id, message_id, 
                        psycopg2.extras.Json(order_details),
                        status, total_amount, currency, 'pending'
                    )
                )
                order_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"Order created: {order_id} for user {user_id}")
                return order_id
                
        except psycopg2.Error as e:
            logger.error(f"Database error in create_order: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
        
        return None

    def create_action_request(
        self,
        user_id: int,
        chatbot_id: int,
        contact_id: int,
        request_type: str,
        request_details: str,
        request_data: Optional[Dict[str, Any]] = None,
        priority: str = 'medium'
    ) -> Optional[int]:
        """
        Creates a new action request for human-in-the-loop workflow.
        Returns action_id on success, None on failure.
        """
        conn = self.connect_to_db()
        if not conn:
            return None

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO actions (
                        user_id, chatbot_id, contact_id, request_type, 
                        request_details, request_data, status, priority
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)
                    RETURNING id
                    """,
                    (
                        user_id, chatbot_id, contact_id, request_type,
                        request_details, 
                        psycopg2.extras.Json(request_data) if request_data else None,
                        priority
                    )
                )
                action_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"Action request created: {action_id} for user {user_id}")
                return action_id
                
        except psycopg2.Error as e:
            logger.error(f"Database error in create_action_request: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
        
        return None

    def track_usage(self, user_id: int, messages_sent: int = 0, campaigns_sent: int = 0) -> bool:
        """Track daily usage for a user."""
        conn = self.connect_to_db()
        if not conn:
            return False

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO usage_tracking (user_id, tracking_date, messages_sent, campaigns_sent)
                    VALUES (%s, CURRENT_DATE, %s, %s)
                    ON CONFLICT (user_id, tracking_date)
                    DO UPDATE SET 
                        messages_sent = usage_tracking.messages_sent + EXCLUDED.messages_sent,
                        campaigns_sent = usage_tracking.campaigns_sent + EXCLUDED.campaigns_sent,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (user_id, messages_sent, campaigns_sent)
                )
                conn.commit()
                return True
                
        except psycopg2.Error as e:
            logger.error(f"Database error in track_usage: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
        
        return False

    def get_user_limits(self, user_id: int) -> Dict[str, int]:
        """Get user's subscription limits."""
        conn = self.connect_to_db()
        if not conn:
            return {'daily_message_limit': 1000, 'monthly_message_limit': 30000}

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT daily_message_limit, monthly_message_limit, 
                           daily_campaign_limit, monthly_campaign_limit
                    FROM user_subscriptions 
                    WHERE user_id = %s AND is_active = true
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (user_id,)
                )
                result = cur.fetchone()
                
                if result:
                    return {
                        'daily_message_limit': result[0],
                        'monthly_message_limit': result[1],
                        'daily_campaign_limit': result[2],
                        'monthly_campaign_limit': result[3]
                    }
                
        except psycopg2.Error as e:
            logger.error(f"Database error in get_user_limits: {e}")
        finally:
            if conn:
                conn.close()
        
        # Return default limits if not found
        return {
            'daily_message_limit': 1000,
            'monthly_message_limit': 30000,
            'daily_campaign_limit': 10,
            'monthly_campaign_limit': 300
        }

    def check_usage_limits(self, user_id: int) -> Dict[str, Any]:
        """Check if user is within their usage limits."""
        conn = self.connect_to_db()
        if not conn:
            return {'within_limits': True, 'limits': {}, 'usage': {}}

        try:
            with conn.cursor() as cur:
                # Get current usage
                cur.execute(
                    """
                    SELECT messages_sent, campaigns_sent
                    FROM usage_tracking 
                    WHERE user_id = %s AND tracking_date = CURRENT_DATE
                    """,
                    (user_id,)
                )
                usage_result = cur.fetchone()
                current_usage = {
                    'daily_messages': usage_result[0] if usage_result else 0,
                    'daily_campaigns': usage_result[1] if usage_result else 0
                }
                
                # Get limits
                limits = self.get_user_limits(user_id)
                
                # Check if within limits
                within_limits = (
                    current_usage['daily_messages'] < limits['daily_message_limit'] and
                    current_usage['daily_campaigns'] < limits['daily_campaign_limit']
                )
                
                return {
                    'within_limits': within_limits,
                    'limits': limits,
                    'usage': current_usage
                }
                
        except psycopg2.Error as e:
            logger.error(f"Database error in check_usage_limits: {e}")
        finally:
            if conn:
                conn.close()
        
        return {'within_limits': True, 'limits': {}, 'usage': {}}

    async def async_update_contact_analytics(self, contact_id: int, analytics_data: Dict[str, Any]) -> bool:
        """
        Asynchronously updates the custom_fields for a contact with new analytics data.
        This uses aiopg for non-blocking database operations.
        """
        try:
            async with aiopg.connect(self.db_url) as conn:
                async with conn.cursor() as cur:
                    # The '||' operator merges the existing JSONB with the new one.
                    query = """
                        UPDATE contacts
                        SET custom_fields = custom_fields || %s::jsonb,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """
                    await cur.execute(query, (json.dumps(analytics_data), contact_id))
                    
                    if cur.rowcount > 0:
                        logger.info(f"Asynchronously updated analytics for contact_id: {contact_id}")
                        return True
                    else:
                        logger.warning(f"Contact {contact_id} not found for async analytics update.")
                        return False
        except Exception as e:
            logger.error(f"Async database error in async_update_contact_analytics: {e}", exc_info=True)
            return False

    def create_order_and_items(self, user_id: int, contact_id: int, shopify_order_data: Dict[str, Any]) -> Optional[int]:
        """
        Creates a new order and its line items in the database within a single transaction.
        Returns the new order_id on success, None on failure.
        """
        conn = self.connect_to_db()
        if not conn:
            return None

        try:
            with conn.cursor() as cur:
                # 1. Create the Order
                order_payload = shopify_order_data['order']
                order_summary = shopify_order_data['order_summary']
                
                cur.execute(
                    """
                    INSERT INTO orders (
                        contact_id, user_id, order_details, status, 
                        total_amount, currency, payment_status, shipping_address, order_notes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        contact_id,
                        user_id,
                        psycopg2.extras.Json(shopify_order_data),  # Store the whole object
                        order_payload.get('status', 'pending'),
                        order_summary.get('total'),
                        order_summary.get('currency', 'USD'),
                        'pending',  # Default payment status
                        psycopg2.extras.Json(shopify_order_data.get('addresses', {}).get('shipping')),
                        shopify_order_data.get('order_notes', '')
                    )
                )
                order_id = cur.fetchone()[0]

                # 2. Create the Order Items
                line_items_payload = shopify_order_data['line_items']
                for item in line_items_payload:
                    cur.execute(
                        """
                        INSERT INTO order_items (
                            order_id, product_name, quantity, unit_price, total_price, item_data
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            order_id,
                            item.get('product_name'),
                            item.get('quantity'),
                            item.get('price'),
                            item.get('price', 0) * item.get('quantity', 1),
                            psycopg2.extras.Json(item)
                        )
                    )
                
                conn.commit()
                logger.info(f"Successfully created order {order_id} and {len(line_items_payload)} line items in the database.")
                return order_id

        except psycopg2.Error as e:
            logger.error(f"Database error in create_order_and_items: {e}", exc_info=True)
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
        
        return None

    def save_order_to_db(self, contact_id: int, user_id: int, shopify_order_data: Dict[str, Any]) -> Optional[int]:
        """
        Simple function to save Shopify order data to Supabase orders table.
        
        Args:
            contact_id: The contact ID who placed the order
            user_id: The user ID (business owner)
            shopify_order_data: The complete Shopify order response data
            
        Returns:
            int: The order ID if successful, None otherwise
        """
        conn = self.connect_to_db()
        if not conn:
            logger.error("Could not connect to database to save order")
            return None
            
        try:
            with conn.cursor() as cur:
                # Extract key order information from Shopify data
                order_details = shopify_order_data.get('order_data', {})
                total_amount = order_details.get('total_price', 0.0)
                order_status = 'confirmed'  # Since Shopify order was successful
                
                # Insert into orders table
                cur.execute("""
                    INSERT INTO orders (contact_id, user_id, order_details, total_amount, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    RETURNING id
                """, (contact_id, user_id, json.dumps(shopify_order_data), total_amount, order_status))
                
                order_id = cur.fetchone()[0]
                conn.commit()
                
                logger.info(f"Order saved to database with ID: {order_id} for contact {contact_id}")
                return order_id
                
        except Exception as e:
            logger.error(f"Database error saving order: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()

    def add_knowledge_base_entry(
        self, 
        user_id: int, 
        chatbot_id: int, 
        category: str, 
        question: str, 
        answer: str
    ) -> bool:
        """
        Add an entry to the bot_knowledge_base table.
        Returns True on success, False on failure.
        """
        conn = self.connect_to_db()
        if not conn:
            return False

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bot_knowledge_base (
                        user_id, chatbot_id, category, question, answer, is_active
                    )
                    VALUES (%s, %s, %s, %s, %s, true)
                    """,
                    (user_id, chatbot_id, category, question, answer)
                )
                conn.commit()
                logger.info(f"Knowledge base entry added for user {user_id}, chatbot {chatbot_id}")
                return True
                
        except psycopg2.Error as e:
            logger.error(f"Database error in add_knowledge_base_entry: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
        
        return False

    def get_all_active_chatbots(self) -> List[Dict[str, Any]]:
        """
        Get all active chatbots with their user_id and id.
        Returns list of dictionaries with chatbot info.
        """
        conn = self.connect_to_db()
        if not conn:
            return []

        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, user_id, name, whatsapp_phone_number
                    FROM chatbots 
                    WHERE is_active = true AND bot_status = 'active'
                    """
                )
                chatbots = cur.fetchall()
                return [dict(chatbot) for chatbot in chatbots]
                
        except psycopg2.Error as e:
            logger.error(f"Database error in get_all_active_chatbots: {e}")
            return []
        finally:
            if conn:
                conn.close()


# Global instance for backward compatibility
db = MultiTenantDB()

# Backward compatibility functions (maintains same interface as old database.py)
def connect_to_db():
    """Backward compatibility function."""
    return db.connect_to_db()

def get_or_create_contact(phone_number: str, name: str = None):
    """Backward compatibility function."""
    return db.get_or_create_contact(phone_number, name=name)

def log_message(contact_id: int, message_id: str, direction: str, message_type: str, 
                content_text: str = None, content_url: str = None, status: str = 'delivered'):
    """Backward compatibility function."""
    return db.log_message(
        contact_id, message_id, direction, message_type,
        content_text=content_text, content_url=content_url, status=status
    )

# New multi-tenant aware functions
def get_user_by_phone_number(phone_number: str):
    """Get user info by phone number mapping."""
    return db.get_user_by_phone_number(phone_number)

def create_action_request(user_id: int, chatbot_id: int, contact_id: int, 
                         request_type: str, request_details: str, **kwargs):
    """Create action request for human intervention."""
    return db.create_action_request(user_id, chatbot_id, contact_id, request_type, request_details, **kwargs)

def track_message_usage(user_id: int):
    """Track a single message for usage limits."""
    return db.track_usage(user_id, messages_sent=1)

def check_message_limits(user_id: int):
    """Check if user can send more messages."""
    return db.check_usage_limits(user_id)

async def async_update_contact_analytics(contact_id: int, analytics_data: Dict[str, Any]):
    """Backward compatibility for async analytics update."""
    return await db.async_update_contact_analytics(contact_id, analytics_data)
 