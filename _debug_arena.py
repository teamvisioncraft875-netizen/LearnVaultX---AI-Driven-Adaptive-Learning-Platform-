import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from flask import Flask, session
from routes.arena import _get_mission_map, leaderboard_api, arena_bp
import sqlite3

class MockDB:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def execute_query(self, query, params=()):
        c = self.conn.cursor()
        c.execute(query, params)
        return [dict(row) for row in c.fetchall()]

    def execute_one(self, query, params=()):
        rows = self.execute_query(query, params)
        return rows[0] if rows else None

# Mock keys
import routes.arena
routes.arena._db = MockDB('education.db')

# Test _get_mission_map
print("--- Testing _get_mission_map ---")
try:
    # Need a valid user ID. Let's find one.
    users = routes.arena._db.execute_query("SELECT id FROM users LIMIT 1")
    if not users:
        print("No users found.")
    else:
        uid = users[0]['id']
        print(f"Using User ID: {uid}")
        
        # Ensure rank status
        routes.arena._ensure_rank_status(uid)
        
        m_map = _get_mission_map(uid)
        print(f"Mission Map: {m_map}")
except Exception as e:
    print(f"Error in _get_mission_map: {e}")
    import traceback
    traceback.print_exc()

print("\n--- Testing Leaderboard Query ---")
try:
    leaders = routes.arena._db.execute_query('''
        SELECT u.username, r.rank_name, r.xp_total, r.level, a.icon as badge_icon
        FROM arena_rank_status r
        JOIN users u ON r.student_id = u.id
        LEFT JOIN arena_achievements a ON a.student_id = r.student_id AND a.unlocked_at = (
            SELECT MAX(unlocked_at) FROM arena_achievements WHERE student_id = r.student_id
        )
        ORDER BY r.xp_total DESC
        LIMIT 10
    ''')
    print(f"Leaders: {leaders}")
except Exception as e:
    print(f"Error in Leaderboard Query: {e}")
    import traceback
    traceback.print_exc()
