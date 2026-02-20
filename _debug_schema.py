import sqlite3

def check_users_schema():
    conn = sqlite3.connect('education.db')
    cursor = conn.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    print("Users Table Schema:")
    for col in columns:
        print(col)
    conn.close()

if __name__ == "__main__":
    check_users_schema()
