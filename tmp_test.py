import sys
sys.stderr = open('error_log.txt', 'w')

from app import app
app.config['TESTING'] = True
app.config['PROPAGATE_EXCEPTIONS'] = True

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['role'] = 'student'
    res = client.post('/arena/start/daily')
