import requests
import os
from flask.sessions import SecureCookieSessionInterface
from app import app
import re

# Create a mock app context to generate session cookie
with app.test_request_context():
    session_interface = SecureCookieSessionInterface()
    serializer = session_interface.get_signing_serializer(app)
    # User 4 (Subrat)
    session_data = {'user_id': 4, 'role': 'student', '_fresh': True}
    val = serializer.dumps(session_data)
    cookie_val = val

print(f"Generated Session Cookie: {cookie_val}")
cookies = {'session': cookie_val}

try:
    print("Requesting...")
    r = requests.get('http://127.0.0.1:5000/arena/daily_challenge', cookies=cookies)
    print(f"Status Code: {r.status_code}")
    
    with open('_debug_output.html', 'w', encoding='utf-8') as f:
        f.write(r.text)
    
    print("Response written to _debug_output.html")
    
    match = re.search(r'window\.QUIZ_DATA\s*=\s*(\{.*?\});', r.text, re.DOTALL)
    if match:
        print("FOUND QUIZ_DATA (partial):")
        print(match.group(1)[:200] + "...")
    else:
        print("QUIZ_DATA NOT FOUND IN RESPONSE")

except Exception as e:
    print(f"Connection Failed: {e}")
