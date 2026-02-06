"""
Database migration script to add missing columns
Run this once to update the existing database
"""
import sqlite3
import sys

def migrate_database(db_path='learnvault.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Add answers column to quiz_submissions if it doesn't exist
        try:
            cursor.execute("ALTER TABLE quiz_submissions ADD COLUMN answers TEXT NOT NULL DEFAULT '{}'")
            print("Added 'answers' column to quiz_submissions")
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e).lower():
                print("'answers' column already exists in quiz_submissions")
            else:
                print(f"Warning: {e}")
        
        # Add provider column to ai_queries if it doesn't exist
        try:
            cursor.execute("ALTER TABLE ai_queries ADD COLUMN provider TEXT DEFAULT 'Groq'")
            print("Added 'provider' column to ai_queries")
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e).lower():
                print("'provider' column already exists in ai_queries")
            else:
                print(f"Warning: {e}")
        
        # Add mode column to ai_queries if it doesn't exist
        try:
            cursor.execute("ALTER TABLE ai_queries ADD COLUMN mode TEXT DEFAULT 'expert'")
            print("Added 'mode' column to ai_queries")
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e).lower():
                print("'mode' column already exists in ai_queries")
            else:
                print(f"Warning: {e}")
        
        conn.commit()
        print("\nDatabase migration completed successfully!")
        
    except Exception as e:
        print(f"\nMigration failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database()
