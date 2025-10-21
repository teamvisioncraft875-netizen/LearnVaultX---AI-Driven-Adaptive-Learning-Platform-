#!/usr/bin/env python3
"""
WSGI entry point for production deployment (Render, Heroku, etc.)
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load secret file from Render if it exists
secret_env_path = '/etc/secrets/.env'
if os.path.exists(secret_env_path):
    load_dotenv(secret_env_path)
    print("Loaded secret file from /etc/secrets/.env")

# Import Flask app
from app import app, init_db

def create_app():
    """Create and configure the Flask application"""
    try:
        # Initialize database if needed
        if not os.path.exists('education.db'):
            print("Creating database...")
            init_db()
            print("Database created successfully!")
        
        return app
    except Exception as e:
        print(f"Error creating app: {e}")
        sys.exit(1)

# WSGI application object for Gunicorn
application = create_app()

if __name__ == '__main__':
    # This won't run in production, but useful for testing
    port = int(os.environ.get('PORT', 5000))
    application.run(host='0.0.0.0', port=port, debug=False)
