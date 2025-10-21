#!/usr/bin/env python3
"""
Simple WSGI entry point for Render
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import Flask app directly
from app import app

# This is what Render will use
application = app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
