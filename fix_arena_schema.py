import sqlite3
import os

DB_PATH = 'education.db'

def fix_schema():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database {DB_PATH} not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tables_to_fix = ['arena_rank_status', 'arena_profiles', 'arena_attempts']
    
    for table in tables_to_fix:
        print(f"--- Checking {table} ---")
        try:
            # Check if updated_at exists
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor.fetchall()]
            
            if not columns:
                print(f"⚠️ Table {table} does not exist. Skipping.")
                continue

            if 'updated_at' not in columns:
                print(f"⚠️ 'updated_at' missing in {table}. Adding it...")
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN updated_at TIMESTAMP")
                    print(f"✅ Added 'updated_at' to {table}")
                except Exception as e:
                    print(f"❌ Failed to add column: {e}")
            else:
                print(f"✅ 'updated_at' already exists in {table}")
                
        except Exception as e:
            print(f"❌ Error inspecting {table}: {e}")

    conn.commit()
    conn.close()
    print("\n✅ Schema fix completed.")

if __name__ == "__main__":
    fix_schema()
