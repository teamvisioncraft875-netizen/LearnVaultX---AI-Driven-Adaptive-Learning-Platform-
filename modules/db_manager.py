import sqlite3
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        
    def get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn
        
    def init_schema(self, schema_path):
        if not os.path.exists(schema_path):
            logger.error(f"Schema file not found: {schema_path}")
            return
            
        try:
            with open(schema_path, 'r') as f:
                schema = f.read()
                
            with self.get_db() as conn:
                conn.executescript(schema)
                conn.commit()
                
            logger.info("Database schema initialized.")
        except Exception as e:
            logger.error(f"Error initializing schema: {e}")
            raise

    def execute_query(self, query, params=()):
        try:
            with self.get_db() as conn:
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Query error: {e}")
            return []

    def execute_one(self, query, params=()):
        try:
            with self.get_db() as conn:
                cursor = conn.execute(query, params)
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Query one error: {e}")
            return None

    def execute_insert(self, query, params=()):
        try:
            with self.get_db() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Insert error: {e}")
            raise

    def execute_update(self, query, params=()):
        try:
            with self.get_db() as conn:
                conn.execute(query, params)
                conn.commit()
        except Exception as e:
            logger.error(f"Update error: {e}")
            raise
