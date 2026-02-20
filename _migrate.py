from ensure_schema import ensure_schema
import os

if __name__ == "__main__":
    db_path = 'education.db'
    if not os.path.exists(db_path):
        print(f"DATABASE NOT FOUND AT {db_path}")
        # Try full path if needed
        db_path = os.path.join(os.getcwd(), 'education.db')
    
    print(f"Migrating {db_path}...")
    try:
        ensure_schema(db_path)
        print("Migration successful.")
    except Exception as e:
        print(f"Migration failed: {e}")
