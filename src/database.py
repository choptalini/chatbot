import os
import uuid
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def connect_to_db():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error connecting to the database: {e}")
        return None

def get_or_create_contact(phone_number: str):
    """
    Retrieves a contact by phone number or creates a new one if not found.
    A new thread_id is created for new contacts.
    """
    conn = connect_to_db()
    if not conn:
        return None, None

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, thread_id FROM contacts WHERE phone_number = %s", (phone_number,))
            contact = cur.fetchone()

            if contact:
                contact_id, thread_id = contact
                return contact_id, thread_id
            else:
                new_thread_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO contacts (phone_number, thread_id) VALUES (%s, %s) RETURNING id",
                    (phone_number, new_thread_id)
                )
                contact_id = cur.fetchone()[0]
                conn.commit()
                return contact_id, new_thread_id
    except psycopg2.Error as e:
        print(f"Database error in get_or_create_contact: {e}")
        return None, None
    finally:
        if conn:
            conn.close()

def log_message(contact_id: int, message_id: str, direction: str, message_type: str, content_text: str = None, content_url: str = None, status: str = 'delivered'):
    """Logs a message to the messages table."""
    conn = connect_to_db()
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (contact_id, message_id, direction, message_type, content_text, content_url, status, sent_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (contact_id, message_id, direction, message_type, content_text, content_url, status)
            )
            conn.commit()
    except psycopg2.Error as e:
        print(f"Database error in log_message: {e}")
    finally:
        if conn:
            conn.close() 