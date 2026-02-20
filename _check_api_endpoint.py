from app import app
from flask import session

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 2  # Assuming ID 2 is a student
        sess['role'] = 'student'
        sess['name'] = 'Subrat'
        sess['_fresh'] = True
    
    print("Testing /api/classes/available...")
    response = client.get('/api/classes/available')
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.get_json()
        print("Response JSON:")
        import json
        print(json.dumps(data, indent=2))
    else:
        print(f"Error: {response.data.decode()}")
