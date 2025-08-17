import psycopg2
import os
from dotenv import load_dotenv
from tabulate import tabulate

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

def fetch_tables(conn):
    """Fetches all tables in the current database."""
    query = """
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_type = 'BASE TABLE'
    ORDER BY table_name;
    """
    
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            tables = cur.fetchall()
            return [table[0] for table in tables]
    except psycopg2.Error as e:
        print(f"Error fetching tables: {e}")
        return []

def fetch_table_schema(conn, table_name):
    """Fetches detailed schema information for a specific table."""
    query = """
    SELECT 
        column_name,
        data_type,
        character_maximum_length,
        is_nullable,
        column_default,
        ordinal_position
    FROM information_schema.columns 
    WHERE table_name = %s 
    AND table_schema = 'public'
    ORDER BY ordinal_position;
    """
    
    try:
        with conn.cursor() as cur:
            cur.execute(query, (table_name,))
            columns = cur.fetchall()
            return columns
    except psycopg2.Error as e:
        print(f"Error fetching schema for table {table_name}: {e}")
        return []

def fetch_constraints(conn, table_name):
    """Fetches constraints for a specific table."""
    query = """
    SELECT 
        tc.constraint_name,
        tc.constraint_type,
        kcu.column_name,
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name
    FROM information_schema.table_constraints AS tc 
    JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    LEFT JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
        AND ccu.table_schema = tc.table_schema
    WHERE tc.table_name = %s 
    AND tc.table_schema = 'public';
    """
    
    try:
        with conn.cursor() as cur:
            cur.execute(query, (table_name,))
            constraints = cur.fetchall()
            return constraints
    except psycopg2.Error as e:
        print(f"Error fetching constraints for table {table_name}: {e}")
        return []

def fetch_indexes(conn, table_name):
    """Fetches indexes for a specific table."""
    query = """
    SELECT 
        indexname,
        indexdef
    FROM pg_indexes 
    WHERE tablename = %s 
    AND schemaname = 'public';
    """
    
    try:
        with conn.cursor() as cur:
            cur.execute(query, (table_name,))
            indexes = cur.fetchall()
            return indexes
    except psycopg2.Error as e:
        print(f"Error fetching indexes for table {table_name}: {e}")
        return []

def display_complete_schema(conn):
    """Displays the complete database schema."""
    print("=" * 80)
    print("DATABASE SCHEMA OVERVIEW")
    print("=" * 80)
    
    tables = fetch_tables(conn)
    
    if not tables:
        print("No tables found in the database.")
        return
    
    print(f"Found {len(tables)} tables: {', '.join(tables)}")
    print()
    
    for table_name in tables:
        print(f"TABLE: {table_name.upper()}")
        print("-" * 60)
        
        # Fetch and display columns
        columns = fetch_table_schema(conn, table_name)
        if columns:
            headers = ["Column", "Type", "Max Length", "Nullable", "Default", "Position"]
            table_data = []
            for col in columns:
                col_name, data_type, max_length, nullable, default, position = col
                max_length_str = str(max_length) if max_length else "N/A"
                default_str = str(default) if default else "None"
                table_data.append([col_name, data_type, max_length_str, nullable, default_str, position])
            
            print("COLUMNS:")
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
            print()
        
        # Fetch and display constraints
        constraints = fetch_constraints(conn, table_name)
        if constraints:
            print("CONSTRAINTS:")
            for constraint in constraints:
                constraint_name, constraint_type, column_name, foreign_table, foreign_column = constraint
                if constraint_type == 'FOREIGN KEY' and foreign_table:
                    print(f"  • {constraint_type}: {column_name} → {foreign_table}.{foreign_column}")
                elif constraint_type == 'PRIMARY KEY':
                    print(f"  • {constraint_type}: {column_name}")
                elif constraint_type == 'UNIQUE':
                    print(f"  • {constraint_type}: {column_name}")
                else:
                    print(f"  • {constraint_type}: {column_name}")
            print()
        
        # Fetch and display indexes
        indexes = fetch_indexes(conn, table_name)
        if indexes:
            print("INDEXES:")
            for index in indexes:
                index_name, index_def = index
                print(f"  • {index_name}: {index_def}")
            print()
        
        print("=" * 60)
        print()

if __name__ == "__main__":
    # Note: You may need to install tabulate: pip install tabulate
    
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("Error: DATABASE_URL environment variable is not set.")
        print("Please set it before running the script.")
        print('Example: export DATABASE_URL="postgresql://user:password@host:port/dbname"')
    else:
        connection = connect_to_db(db_url)
        if connection:
            display_complete_schema(connection)
            connection.close()
            print("Database connection closed.") 