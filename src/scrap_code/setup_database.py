import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

def connect_to_db(db_url):
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(db_url)
        print("Successfully connected to the database.")
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error: Could not connect to the database. {e}")
        return None

def create_tables(conn):
    """Creates the necessary tables in the database."""
    sql_commands = """
    CREATE TABLE IF NOT EXISTS contacts (
        id SERIAL PRIMARY KEY,
        phone_number VARCHAR(255) UNIQUE NOT NULL,
        name VARCHAR(255),
        thread_id VARCHAR(255) UNIQUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        message_id VARCHAR(255) UNIQUE NOT NULL,
        contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
        direction VARCHAR(10) NOT NULL CHECK (direction IN ('incoming', 'outgoing')),
        message_type VARCHAR(50) NOT NULL,
        content_text TEXT,
        content_url VARCHAR(2048),
        status VARCHAR(50),
        sent_at TIMESTAMP WITH TIME ZONE NOT NULL,
        metadata JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
        message_id INTEGER REFERENCES messages(id),
        order_details JSONB,
        status VARCHAR(50) NOT NULL DEFAULT 'pending',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS campaigns (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        type VARCHAR(50) NOT NULL,
        message_template TEXT NOT NULL,
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS campaign_subscribers (
        id SERIAL PRIMARY KEY,
        campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
        contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
        status VARCHAR(50) DEFAULT 'subscribed' CHECK (status IN ('subscribed', 'unsubscribed')),
        subscribed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (campaign_id, contact_id)
    );

    CREATE INDEX IF NOT EXISTS idx_messages_contact_id ON messages(contact_id);
    CREATE INDEX IF NOT EXISTS idx_orders_contact_id ON orders(contact_id);
    """
    
    try:
        with conn.cursor() as cur:
            cur.execute(sql_commands)
        conn.commit()
        print("Tables created successfully (or already exist).")
    except psycopg2.Error as e:
        print(f"Error creating tables: {e}")
        conn.rollback()

if __name__ == "__main__":
    # Ensure you have psycopg2-binary installed: pip install psycopg2-binary
    # Make sure to set your DATABASE_URL as an environment variable
    
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("Error: DATABASE_URL environment variable is not set.")
        print("Please set it before running the script.")
        print('Example: export DATABASE_URL="postgresql://user:password@host:port/dbname"')
    else:
        connection = connect_to_db(db_url)
        if connection:
            create_tables(connection)
            connection.close()
            print("Database connection closed.") 