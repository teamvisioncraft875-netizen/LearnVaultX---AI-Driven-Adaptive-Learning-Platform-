import sqlite3

def check_schema():
    conn = sqlite3.connect('education.db')
    cursor = conn.cursor()
    
    tables = ['arena_rank_status', 'arena_profiles', 'arena_attempts']
    
    for table in tables:
        print(f"\n--- Checking {table} ---")
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            col_names = [c[1] for c in columns]
            
            if not col_names:
                 print(f"⚠️ Table {table} NOT FOUND or empty")
                 continue
                 
            if 'updated_at' in col_names:
                print(f"✅ 'updated_at' FOUND in {table}")
            else:
                print(f"❌ 'updated_at' MISSING in {table}")
                params = [c[1] for c in columns]
                print(f"   Existing columns: {params}")
        except Exception as e:
            print(f"Error checking {table}: {e}")

    conn.close()

if __name__ == "__main__":
    check_schema()
