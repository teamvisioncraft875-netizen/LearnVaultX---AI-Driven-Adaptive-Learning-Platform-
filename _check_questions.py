from app import app
from modules import db_manager

db = db_manager.DatabaseManager('education.db')

print("Checking Arena Question Bank...")
count = db.execute_one("SELECT COUNT(*) as cnt FROM arena_question_bank")
print(f"Total Questions: {count['cnt']}")

print("\nChecking Users...")
users = db.execute_query("SELECT id, name, email, role FROM users")
for u in users:
    print(f"User {u['id']}: {u['name']} ({u['email']}) - {u['role']}")


print("\nChecking Question Bank Categories...")
cats = db.execute_query("SELECT DISTINCT exam, subject FROM arena_question_bank")
for c in cats:
    print(f"Category: '{c['exam']}' / '{c['subject']}'")

except Exception as e:
    print(f"Error: {e}")
