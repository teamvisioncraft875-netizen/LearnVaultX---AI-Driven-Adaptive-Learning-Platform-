import sqlite3
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

def migrate_data():
    load_dotenv()
    pg_url = os.getenv('DATABASE_URL')
    
    if not pg_url:
        print("ERROR: No DATABASE_URL found in environment.")
        return

    print("Connecting to SQLite database (education.db)...")
    try:
        sqlite_conn = sqlite3.connect('education.db')
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()
    except Exception as e:
        print(f"Failed to connect to SQLite: {e}")
        return

    print(f"Connecting to PostgreSQL ({pg_url})...")
    try:
        pg_conn = psycopg2.connect(pg_url)
        pg_cursor = pg_conn.cursor()
    except Exception as e:
        print(f"Failed to connect to PostgreSQL: {e}")
        return

    # List of tables to migrate manually based on models.py
    # Ordered roughly by dependency to avoid foreign key issues if ON CONFLICT DO NOTHING fails
    # However we'll temporarily disable foreign key checks in PG for the transaction
    
    sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    sqlite_tables = [row['name'] for row in sqlite_cursor.fetchall() 
                     if row['name'] not in ('alembic_version', 'sqlite_sequence')]

    print(f"Found {len(sqlite_tables)} tables in SQLite.")
    
    # Disable foreign key triggers for the session to make migration easier
    pg_cursor.execute("SET session_replication_role = 'replica';")

    for table in sqlite_tables:
        print(f"\nProcessing table: {table}")
        
        # Check if table exists in PostgreSQL
        pg_cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s);", (table,))
        if not pg_cursor.fetchone()[0]:
            print(f"  Skipping '{table}' - does not exist in PostgreSQL schema.")
            continue
            
        sqlite_cursor.execute(f"SELECT * FROM {table}")
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            print(f"  Skipping '{table}' - empty in SQLite.")
            continue
            
        columns = rows[0].keys()
        col_str = ', '.join(columns)
        val_placeholders = ', '.join(['%s'] * len(columns))
        
        insert_query = f"INSERT INTO {table} ({col_str}) VALUES ({val_placeholders}) ON CONFLICT DO NOTHING"
        
        data_to_insert = [tuple(row) for row in rows]
            
        try:
            psycopg2.extras.execute_batch(pg_cursor, insert_query, data_to_insert)
            pg_conn.commit()
            print(f"  ✔ Migrated {len(rows)} rows into '{table}'.")
            
            # Reset ID sequence if the table has an 'id' column
            if 'id' in columns:
                try:
                    seq_name = f"{table}_id_seq"
                    pg_cursor.execute(f"SELECT setval('{seq_name}', COALESCE((SELECT MAX(id)+1 FROM {table}), 1), false);")
                    pg_conn.commit()
                except Exception as seq_err:
                    pg_conn.rollback()
                    # It's fine if it fails, not all tables use standard sequences or have 'id_seq'
                    pass
                    
        except Exception as e:
            pg_conn.rollback()
            print(f"  ❌ Error migrating '{table}': {e}")

    # Re-enable foreign key triggers
    pg_cursor.execute("SET session_replication_role = 'origin';")
    pg_conn.commit()

    pg_cursor.close()
    pg_conn.close()
    sqlite_cursor.close()
    sqlite_conn.close()

    print("\nMigration completed successfully!")

if __name__ == "__main__":
    migrate_data()
