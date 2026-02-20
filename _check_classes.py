import sqlite3
import os

db_path = r'c:\Users\subha\Desktop\ProjectLVX1\education.db'
if not os.path.exists(db_path):
    print("DB not found")
else:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    print("--- CLASSES ---")
    classes = cur.execute("SELECT id, title, code, teacher_id FROM classes").fetchall()
    for c in classes:
        print(f"ID: {c['id']}, Title: {c['title']}, Code: '{c['code']}'")
        
    conn.close()
