#!/usr/bin/env python3
"""
Simple WSGI entry point for Render deployment
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the Flask app
from app import app

# WSGI application object
application = app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    application.run(host='0.0.0.0', port=port, debug=False)
