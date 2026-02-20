import sqlite3
import os

DB_PATH = 'education.db'

def create_table():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database {DB_PATH} not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        print("--- Creating arena_profiles if missing ---")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS arena_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                exam TEXT NOT NULL DEFAULT 'JEE',
                subject TEXT NOT NULL DEFAULT 'Physics',
                mode TEXT NOT NULL DEFAULT 'Practice',
                preferred_difficulty TEXT NOT NULL DEFAULT 'Auto',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                UNIQUE(student_id)
            );
        """)
        print("✅ executed CREATE TABLE IF NOT EXISTS arena_profiles")
        
        # Verify it exists now
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='arena_profiles'")
        if cursor.fetchone():
            print("✅ Verified: arena_profiles exists.")
        else:
            print("❌ Failed to create arena_profiles.")
            
        conn.commit()
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_table()
