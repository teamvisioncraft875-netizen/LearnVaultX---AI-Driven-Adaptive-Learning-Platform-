from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import json
import time
import logging
import random
import string
from dotenv import load_dotenv

def generate_class_code():
    """Generate a unique 6-character alphanumeric code"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# Load environment variables from .env file BEFORE importing modules that use them
load_dotenv()

from modules import db_manager, adaptive_learning_new, email_service, kyknox_ai_new, demo_data_generator
from modules.micro_learning_manager import MicroLearningManager
from modules.adaptive_quiz_generator import AdaptiveQuizGenerator
from modules.skill_tree_engine import SkillTreeEngine
from modules.exam_predictor import ExamPredictor
from modules.leaderboard_engine import LeaderboardEngine

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-change-in-production')

# App version for cache busting
app.config['APP_VERSION'] = '2.0.1'

# Configure Session Cookies
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True

# Configure Uploads
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB Limit

# Initialize Services
db = db_manager.DatabaseManager('education.db')

# Ensure all required tables & columns exist (safe to re-run)
from ensure_schema import ensure_schema
ensure_schema('education.db')

adaptive = adaptive_learning_new.AdaptiveEngine(db)
kyknox = kyknox_ai_new.KyKnoX()
micro_learning = MicroLearningManager(db, adaptive, kyknox)
adaptive_quiz = AdaptiveQuizGenerator(db, kyknox, adaptive)
skill_tree = SkillTreeEngine(db, kyknox)
exam_predictor = ExamPredictor(db)
leaderboard_engine = LeaderboardEngine(db)
data_generator = demo_data_generator.DemoDataGenerator(db)

# Initialize Learning Path Service
from modules import learning_path, badges
learning_path_service = learning_path.LearningPathService(db, adaptive_engine=adaptive)
badge_service = badges.BadgeService(db)

# Initialize AI Tutor Blueprint
from routes.ai_tutor import ai_tutor_bp, init_ai_tutor
init_ai_tutor(db, adaptive, kyknox, learning_path_service)
app.register_blueprint(ai_tutor_bp)

# Initialize Exam Arena Blueprint
from routes.arena import arena_bp, init_arena
init_arena(db, kyknox)
app.register_blueprint(arena_bp)


# Custom Jinja Filters
app.jinja_env.filters['from_json'] = json.loads

# Initialize SocketIO with threading mode for Windows compatibility
# Using 'threading' instead of 'eventlet' to avoid Windows-specific issues
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add cache control headers for development (disable caching)
@app.after_request
def add_no_cache_headers(response):
    """Disable caching in debug mode to ensure latest code is always served"""
    if app.debug:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

# Helper Functions
def get_current_user_id():
    return session.get('user_id')

def login_required(f):
    """Decorator for page routes - redirects to login"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def api_login_required(f):
    """Decorator for API routes - returns JSON 401 instead of redirecting"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Unauthorized', 'message': 'Please login to continue'}), 401
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'teacher':
            return "Access denied: Teachers only", 403
        return f(*args, **kwargs)
    return decorated_function

def api_teacher_required(f):
    """Decorator for API routes requiring teacher role - returns JSON 403"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'teacher':
            return jsonify({'success': False, 'error': 'Forbidden', 'message': 'Teachers only'}), 403
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    """Decorator to require login for page and API routes."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Authentication required'}), 401
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    """Decorator to require teacher role."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'teacher':
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Teacher access required'}), 403
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    """Decorator to require student role."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'student':
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Student access required'}), 403
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function



def rate_limit(calls=5, period=60):
    """Simple per-session rate limit decorator.

    calls: number of allowed calls within period (seconds)
    period: time window in seconds
    """
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            key = f'rl:{f.__name__}'
            now = time.time()
            store = session.setdefault('_rate_limits', {})
            timestamps = store.get(key, [])
            # Remove expired
            timestamps = [t for t in timestamps if now - t < period]
            if len(timestamps) >= calls:
                return jsonify({'success': False, 'error': 'Too Many Requests', 'message': 'Rate limit exceeded'}), 429
            timestamps.append(now)
            store[key] = timestamps
            session['_rate_limits'] = store
            return f(*args, **kwargs)
        return wrapped
    return decorator

# Standard JSON response helpers
def json_success(message='OK', data=None, status=200, **extra):
    payload = {'success': True, 'message': message, 'data': data if data is not None else {}}
    payload.update(extra)
    return jsonify(payload), status


def json_error(message='Request failed', status=400, error=None, data=None, **extra):
    payload = {'success': False, 'message': message, 'error': error or message, 'data': data if data is not None else {}}
    payload.update(extra)
    return jsonify(payload), status


def get_json_payload():
    if not request.is_json:
        return None
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def table_exists(table_name):
    row = db.execute_one(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,)
    )
    return bool(row)

# Input Sanitization
def sanitize_input(text, max_length=1000):
    if not text:
        return ""
    import html
    text = str(text).strip()
    # Basic HTML escaping
    text = html.escape(text)
    return text[:max_length]

# Validation Helpers
def validate_email(email):
    import re
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def validate_password(password):
    if len(password) < 6:
        return False, "Password must be at least 6 characters"
    return True, ""

def validate_file_type(filename, allowed_extensions):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def validate_quiz_data(data):
    if not data.get('title'):
        return False, "Quiz title required"
    
    questions = data.get('questions')
    if not questions or not isinstance(questions, list) or len(questions) == 0:
        return False, "At least one question required (must be a list)"
    
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            return False, f"Question {i+1} must be an object"
            
        if not q.get('question'):
            return False, f"Question {i+1} text is missing"
            
        options = q.get('options')
        if not options or not isinstance(options, list) or len(options) < 2:
            return False, f"Question {i+1} must have at least 2 options"
            
        correct = q.get('correct')
        if correct is None:
            return False, f"Question {i+1} missing correct answer index"
            
        try:
            correct_idx = int(correct)
            if correct_idx < 0 or correct_idx >= len(options):
                return False, f"Question {i+1} correct index out of bounds"
        except (ValueError, TypeError):
            return False, f"Question {i+1} correct index must be a number"
            
    return True, ""

def hash_password(password):
    # Use werkzeug's strong PBKDF2 hashing
    return generate_password_hash(password)


def verify_password(stored_hash, password, user_id=None):
    """Verify password against stored hash.

    Supports legacy SHA-256 hex digests by auto-upgrading the hash to a secure PBKDF2 hash on successful login.
    If `user_id` is provided and a legacy hash is detected and validated, the DB will be updated.
    """
    if not stored_hash:
        return False

    try:
        # If stored_hash looks like a werkzeug hash (contains ':' or starts with method) use check_password_hash
        # werkzeug hashes have format: method:salt:hash or scrypt:iterations:blocksize:parallelization$salt$...
        if ':' in stored_hash or stored_hash.startswith('$'):
            logger.info(f"[VERIFY] Using werkzeug check_password_hash for hash type: {stored_hash[:20]}")
            result = check_password_hash(stored_hash, password)
            logger.info(f"[VERIFY] werkzeug result: {result}")
            return result
    except Exception as e:
        logger.exception(f"[VERIFY] Exception in werkzeug check: {e}")
        # Fallback to legacy handling below
        pass

    # Legacy SHA-256 hex digest: compare and upgrade if user_id provided
    try:
        import hashlib
        legacy = hashlib.sha256(password.encode()).hexdigest()
        if legacy == stored_hash:
            # Optionally upgrade stored hash to werkzeug format
            if user_id:
                try:
                    new_hash = generate_password_hash(password)
                    db.execute_update('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user_id))
                    logger.info(f"Upgraded password hash for user {user_id} to PBKDF2")
                except Exception:
                    logger.exception('Failed to upgrade legacy password hash')
            return True
    except Exception:
        pass

    return False

# ============================================================================
# AUTH ROUTES
# ============================================================================

@app.route('/')
def index():
    if 'user_id' in session:
        if session['role'] == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        return redirect(url_for('student_dashboard'))
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next', '')
    if request.method == 'POST':
        # Handled by API
        return render_template('login.html', next=next_url)
    return render_template('login.html', next=next_url)

@app.route('/api/login', methods=['POST'])
@rate_limit(calls=6, period=60)
def api_login():
    data = get_json_payload()
    if data is None:
        return json_error('Invalid JSON payload', status=400)
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return json_error('Email and password required', status=400)

    user = db.execute_one('SELECT * FROM users WHERE email = ?', (email,))
    logger.info(f"[LOGIN] User lookup for {email}: Found={user is not None}")

    if not user or not verify_password(user['password_hash'], password, user_id=user['id']):
        return json_error('Invalid credentials', status=401)

    # Check if user is verified
    if not user.get('is_verified'):
        # Store next parameter for OTP flow
        next_url = data.get('next', '')
        if next_url:
            session['login_next'] = next_url
        return json_error('Please verify your email first. Sign up again to receive a new verification code.', status=403)

    # Credentials valid + verified → Log in directly (Bypass OTP)
    session['user_id'] = user['id']
    session['name'] = user['name']
    session['role'] = user['role']
    session['email'] = user['email']

    # Honor next parameter for post-login redirect (e.g. /arena)
    next_url = data.get('next', '')
    # Handle both full URLs and relative paths
    if next_url:
        from urllib.parse import urlparse
        parsed = urlparse(next_url)
        # Extract just the path portion for safety
        safe_next = parsed.path if parsed.path else ''
        if safe_next and safe_next.startswith('/'):
            redirect_url = safe_next
        else:
            redirect_url = '/teacher/dashboard' if user['role'] == 'teacher' else '/student/dashboard'
    else:
        redirect_url = '/teacher/dashboard' if user['role'] == 'teacher' else '/student/dashboard'
    logger.info(f"[LOGIN] User {email} logged in successfully (OTP bypassed), redirect={redirect_url}")
    
    return jsonify({
        'success': True,
        'message': 'Login successful',
        'redirect': redirect_url,
        'user': {'id': user['id'], 'name': user['name'], 'role': user['role']}
    }), 200

@app.route('/register', methods=['GET'])
def register():
    return render_template('register.html')

@app.route('/api/register', methods=['POST'])
@rate_limit(calls=6, period=60)
def api_register():
    data = get_json_payload()
    if data is None:
        return json_error('Invalid JSON payload', status=400)
    name = sanitize_input(data.get('name'))
    email = data.get('email', '').strip().lower()
    password = data.get('password')
    role = data.get('role', 'student')

    if not name or not email or not password:
        return json_error('All fields required', status=400)

    if not validate_email(email):
        return json_error('Invalid email format', status=400)

    is_valid, error_msg = validate_password(password)
    if not is_valid:
        return json_error(error_msg, status=400)

    if role not in ('student', 'teacher'):
        return json_error('Invalid role', status=400)

    # Check if user exists
    existing = db.execute_one('SELECT id, is_verified FROM users WHERE email = ?', (email,))
    if existing:
        if existing.get('is_verified'):
            return json_error('Email already registered', status=400)
        else:
            # Unverified user re-signing up — delete old record so they can re-register
            db.execute_update('DELETE FROM users WHERE email = ? AND is_verified = 0', (email,))

    # Create user as UNVERIFIED
    password_hash = hash_password(password)
    logger.info(f"[REGISTER] Creating unverified user {email}")
    user_id = db.execute_insert(
        'INSERT INTO users (name, email, password_hash, role, is_verified) VALUES (?, ?, ?, ?, 0)',
        (name, email, password_hash, role)
    )

    # Generate and send signup OTP
    otp = email_service.generate_otp()
    otp_hash = email_service.hash_otp(otp)
    expires_at = email_service.get_otp_expiry()

    # Invalidate old signup OTPs
    db.execute_update(
        "UPDATE otp_requests SET is_used = 1 WHERE email = ? AND otp_type = 'signup' AND is_used = 0",
        (email,)
    )

    db.execute_insert(
        'INSERT INTO otp_requests (email, otp_hash, otp_type, expires_at) VALUES (?, ?, ?, ?)',
        (email, otp_hash, 'signup', expires_at)
    )

    email_sent = email_service.send_otp_email(email, otp, purpose='signup')
    if not email_sent:
        logger.error(f"[REGISTER] Failed to send signup OTP to {email}")
        return json_error('Failed to send OTP email. Please try again later.', status=500)

    # Store signup context in session
    session['signup_otp_email'] = email
    session['signup_otp_user_id'] = user_id
    session.pop('user_id', None)

    logger.info(f"[REGISTER] Signup OTP sent to {email}")
    return jsonify({
        'success': True,
        'message': 'OTP sent to your email for verification',
        'redirect': '/verify-signup-otp'
    }), 200

# ============================================================================
# SIGNUP OTP VERIFICATION
# ============================================================================

@app.route('/verify-signup-otp')
def verify_signup_otp_page():
    """Render signup OTP verification page."""
    if 'signup_otp_email' not in session:
        return redirect(url_for('register'))
    return render_template('verify_signup_otp.html')

@app.route('/api/verify-signup-otp', methods=['POST'])
@rate_limit(calls=10, period=120)
def api_verify_signup_otp():
    """Verify signup OTP and activate user account."""
    data = get_json_payload()
    if data is None:
        return json_error('Invalid JSON payload', status=400)

    email = session.get('signup_otp_email', '')
    otp = data.get('otp', '').strip()

    if not email:
        return json_error('Session expired. Please sign up again.', status=400)
    if not otp or len(otp) != 6:
        return json_error('Please enter a valid 6-digit OTP', status=400)

    # Get latest unused signup OTP
    otp_record = db.execute_one(
        "SELECT * FROM otp_requests WHERE email = ? AND otp_type = 'signup' AND is_used = 0 ORDER BY created_at DESC LIMIT 1",
        (email,)
    )

    if not otp_record:
        return json_error('No active OTP found. Please request a new one.', status=400)

    # Check attempts
    attempts = otp_record.get('attempts', 0) or 0
    if attempts >= 5:
        db.execute_update('UPDATE otp_requests SET is_used = 1 WHERE id = ?', (otp_record['id'],))
        return json_error('Too many attempts. Please sign up again.', status=429)

    # Check expiry
    try:
        expires_at = datetime.fromisoformat(str(otp_record['expires_at']))
        if datetime.now() > expires_at:
            db.execute_update('UPDATE otp_requests SET is_used = 1 WHERE id = ?', (otp_record['id'],))
            return json_error('OTP has expired. Please request a new one.', status=400)
    except (ValueError, TypeError):
        return json_error('OTP record invalid. Please sign up again.', status=400)

    # Increment attempts
    db.execute_update('UPDATE otp_requests SET attempts = ? WHERE id = ?', (attempts + 1, otp_record['id']))

    # Verify OTP hash
    if not email_service.verify_otp(otp_record['otp_hash'], otp):
        remaining = 4 - attempts
        if remaining > 0:
            return json_error(f'Incorrect OTP. {remaining} attempt(s) remaining.', status=400)
        else:
            db.execute_update('UPDATE otp_requests SET is_used = 1 WHERE id = ?', (otp_record['id'],))
            return json_error('Too many failed attempts. Please sign up again.', status=429)

    # OTP verified — activate user
    db.execute_update('UPDATE otp_requests SET is_used = 1 WHERE id = ?', (otp_record['id'],))
    db.execute_update(
        'UPDATE users SET is_verified = 1, verified_at = ? WHERE email = ?',
        (datetime.now().isoformat(), email)
    )

    # Clear signup session
    session.pop('signup_otp_email', None)
    session.pop('signup_otp_user_id', None)

    logger.info(f"[REGISTER] Email verified for {email}")
    return json_success('Email verified! You can now log in.', redirect='/login')

@app.route('/api/resend-signup-otp', methods=['POST'])
@rate_limit(calls=3, period=120)
def resend_signup_otp():
    """Resend signup OTP with 60s cooldown."""
    email = session.get('signup_otp_email', '')
    if not email:
        return json_error('Session expired. Please sign up again.', status=400)

    # 60s cooldown
    last = db.execute_one(
        "SELECT created_at FROM otp_requests WHERE email = ? AND otp_type = 'signup' ORDER BY created_at DESC LIMIT 1",
        (email,)
    )
    if last:
        try:
            elapsed = (datetime.now() - datetime.fromisoformat(str(last['created_at']))).total_seconds()
            if elapsed < 60:
                return json_error(f'Please wait {int(60 - elapsed)} seconds before resending', status=429)
        except (ValueError, TypeError):
            pass

    # Invalidate old + send new
    db.execute_update("UPDATE otp_requests SET is_used = 1 WHERE email = ? AND otp_type = 'signup' AND is_used = 0", (email,))
    otp = email_service.generate_otp()
    otp_hash = email_service.hash_otp(otp)
    expires_at = email_service.get_otp_expiry()
    db.execute_insert('INSERT INTO otp_requests (email, otp_hash, otp_type, expires_at) VALUES (?, ?, ?, ?)',
                      (email, otp_hash, 'signup', expires_at))
    email_sent = email_service.send_otp_email(email, otp, purpose='signup')
    if not email_sent:
        return json_error('Failed to send email', status=500)
    logger.info(f"[REGISTER] Resent signup OTP to {email}")
    return json_success('New OTP sent to your email')

# ============================================================================
# LOGIN OTP VERIFICATION
# ============================================================================

@app.route('/verify-login-otp')
def verify_login_otp_page():
    """Render login OTP verification page."""
    if 'login_otp_email' not in session:
        return redirect(url_for('login'))
    return render_template('verify_login_otp.html')

@app.route('/api/verify-login-otp', methods=['POST'])
@rate_limit(calls=10, period=120)
def api_verify_login_otp():
    """Verify login OTP and create session."""
    data = get_json_payload()
    if data is None:
        return json_error('Invalid JSON payload', status=400)

    email = session.get('login_otp_email', '')
    otp = data.get('otp', '').strip()

    if not email:
        return json_error('Session expired. Please log in again.', status=400)
    if not otp or len(otp) != 6:
        return json_error('Please enter a valid 6-digit OTP', status=400)

    # Get latest unused login OTP
    otp_record = db.execute_one(
        "SELECT * FROM otp_requests WHERE email = ? AND otp_type = 'login' AND is_used = 0 ORDER BY created_at DESC LIMIT 1",
        (email,)
    )

    if not otp_record:
        return json_error('No active OTP found. Please log in again.', status=400)

    # Check attempts
    attempts = otp_record.get('attempts', 0) or 0
    if attempts >= 5:
        db.execute_update('UPDATE otp_requests SET is_used = 1 WHERE id = ?', (otp_record['id'],))
        return json_error('Too many attempts. Please log in again.', status=429)

    # Check expiry
    try:
        expires_at = datetime.fromisoformat(str(otp_record['expires_at']))
        if datetime.now() > expires_at:
            db.execute_update('UPDATE otp_requests SET is_used = 1 WHERE id = ?', (otp_record['id'],))
            return json_error('OTP has expired. Please log in again.', status=400)
    except (ValueError, TypeError):
        return json_error('OTP record invalid. Please log in again.', status=400)

    # Increment attempts
    db.execute_update('UPDATE otp_requests SET attempts = ? WHERE id = ?', (attempts + 1, otp_record['id']))

    # Verify OTP hash
    if not email_service.verify_otp(otp_record['otp_hash'], otp):
        remaining = 4 - attempts
        if remaining > 0:
            return json_error(f'Incorrect OTP. {remaining} attempt(s) remaining.', status=400)
        else:
            db.execute_update('UPDATE otp_requests SET is_used = 1 WHERE id = ?', (otp_record['id'],))
            return json_error('Too many failed attempts. Please log in again.', status=429)

    # OTP verified — create login session
    db.execute_update('UPDATE otp_requests SET is_used = 1 WHERE id = ?', (otp_record['id'],))

    user_id = session.get('login_otp_user_id')
    name = session.get('login_otp_name')
    role = session.get('login_otp_role')

    # Create real session
    session['user_id'] = user_id
    session['name'] = name
    session['role'] = role
    session['email'] = email

    # Clear OTP session keys and retrieve preserved next URL
    next_url = session.pop('login_next', '')
    for key in ['login_otp_email', 'login_otp_user_id', 'login_otp_name', 'login_otp_role']:
        session.pop(key, None)

    # Honor next parameter for post-login redirect (e.g. /arena)
    if next_url:
        from urllib.parse import urlparse
        parsed = urlparse(next_url)
        safe_next = parsed.path if parsed.path else ''
        if safe_next and safe_next.startswith('/'):
            redirect_url = safe_next
        else:
            redirect_url = '/teacher/dashboard' if role == 'teacher' else '/student/dashboard'
    else:
        redirect_url = '/teacher/dashboard' if role == 'teacher' else '/student/dashboard'
    logger.info(f"[LOGIN] Login OTP verified for {email}, redirecting to {redirect_url}")
    return jsonify({
        'success': True,
        'message': 'Login successful',
        'redirect': redirect_url,
        'user': {'id': user_id, 'name': name, 'role': role}
    }), 200

@app.route('/api/resend-login-otp', methods=['POST'])
@rate_limit(calls=3, period=120)
def resend_login_otp():
    """Resend login OTP with 60s cooldown."""
    email = session.get('login_otp_email', '')
    if not email:
        return json_error('Session expired. Please log in again.', status=400)

    # 60s cooldown
    last = db.execute_one(
        "SELECT created_at FROM otp_requests WHERE email = ? AND otp_type = 'login' ORDER BY created_at DESC LIMIT 1",
        (email,)
    )
    if last:
        try:
            elapsed = (datetime.now() - datetime.fromisoformat(str(last['created_at']))).total_seconds()
            if elapsed < 60:
                return json_error(f'Please wait {int(60 - elapsed)} seconds before resending', status=429)
        except (ValueError, TypeError):
            pass

    # Invalidate old + send new
    db.execute_update("UPDATE otp_requests SET is_used = 1 WHERE email = ? AND otp_type = 'login' AND is_used = 0", (email,))
    otp = email_service.generate_otp()
    otp_hash = email_service.hash_otp(otp)
    expires_at = email_service.get_otp_expiry()
    db.execute_insert('INSERT INTO otp_requests (email, otp_hash, otp_type, expires_at) VALUES (?, ?, ?, ?)',
                      (email, otp_hash, 'login', expires_at))
    email_sent = email_service.send_otp_email(email, otp, purpose='login')
    if not email_sent:
        logger.error(f"[LOGIN] Failed to resend login OTP to {email}")
        return json_error('Failed to send email. Please try again later.', status=500)
    logger.info(f"[LOGIN] Resent login OTP to {email}")
    return json_success('New OTP sent to your email')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/health')
def health_check():
    """Health check endpoint to verify backend is running"""
    return jsonify({
        'status': 'ok',
        'message': 'LearnVaultX backend is running',
        'database': 'education.db',
        'timestamp': datetime.now().isoformat()
    }), 200



@app.route('/api/speed-test')
def speed_test():
    """Returns random data for speed testing."""
    try:
        size = int(request.args.get('size', 50000)) # Default 50KB
        if size > 5000000: # Max 5MB
            size = 5000000
        # Generate random bytes efficiently
        data = os.urandom(size)
        return data, 200, {
            'Content-Type': 'application/octet-stream',
            'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'
        }
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/test-connection')
def test_connection():
    """Test page to verify backend connection"""
    return render_template('test_connection.html')

# ============================================================================
# FORGOT PASSWORD — OTP FLOW
# ============================================================================

@app.route('/forgot-password')
def forgot_password_page():
    """Render the forgot-password email entry page."""
    return render_template('forgot_password.html')

@app.route('/verify-otp')
def verify_otp_page():
    """Render OTP verification page. Requires email in session."""
    if 'reset_email' not in session:
        return redirect(url_for('forgot_password_page'))
    return render_template('verify_otp.html')

@app.route('/reset-password')
def reset_password_page():
    """Render password reset page. Requires verified OTP."""
    if not session.get('otp_verified'):
        return redirect(url_for('forgot_password_page'))
    return render_template('reset_password.html')


@app.route('/api/forgot-password/send-otp', methods=['POST'])
@rate_limit(calls=5, period=120)
def send_password_reset_otp():
    """Send OTP for password reset."""
    try:
        logger.info("[FORGOT-PW] Forgot password request received")

        data = get_json_payload()
        if data is None:
            return json_error('Invalid JSON payload', status=400)

        email = data.get('email', '').lower().strip()
        logger.info(f"[FORGOT-PW] Email received: {email}")

        if not email or not validate_email(email):
            return json_error('Valid email address required', status=400)

        # Check if user exists
        user = db.execute_one('SELECT id FROM users WHERE email = ?', (email,))
        if not user:
            logger.info(f"[FORGOT-PW] Email not found in DB: {email}")
            # Security: don't reveal whether email exists
            return json_success('If this email is registered, an OTP has been sent.')

        logger.info(f"[FORGOT-PW] User found for {email}")

        # Rate-limit: prevent spam — check last OTP sent time
        last_otp = db.execute_one(
            'SELECT created_at FROM password_reset_otp WHERE email = ? ORDER BY created_at DESC LIMIT 1',
            (email,)
        )
        if last_otp:
            try:
                last_time = datetime.fromisoformat(str(last_otp['created_at']))
                if (datetime.now() - last_time).total_seconds() < 60:
                    return json_error('Please wait before requesting another OTP', status=429)
            except (ValueError, TypeError):
                pass  # Proceed if timestamp parsing fails

        # Generate OTP
        otp = email_service.generate_otp()
        otp_hash = email_service.hash_otp(otp)
        expires_at = email_service.get_otp_expiry()
        logger.info(f"[FORGOT-PW] OTP generated for {email}")

        # Invalidate old OTPs for this email
        db.execute_update(
            'UPDATE password_reset_otp SET used = 1 WHERE email = ? AND used = 0',
            (email,)
        )

        # Store hashed OTP
        db.execute_insert(
            'INSERT INTO password_reset_otp (email, otp, expires_at, used, attempts) VALUES (?, ?, ?, 0, 0)',
            (email, otp_hash, expires_at)
        )
        logger.info(f"[FORGOT-PW] OTP stored in DB for {email}")

        # Send email (real SMTP or console fallback)
        logger.info(f"[FORGOT-PW] Sending OTP email to {email}...")
        if email_service.send_otp_email(email, otp):
            # Store email in session for flow continuity
            session['reset_email'] = email
            session.pop('otp_verified', None)
            logger.info(f"[FORGOT-PW] OTP email sent successfully to {email}")
            return json_success('OTP sent to your email address')
        else:
            logger.error(f"[FORGOT-PW] Failed to send OTP email to {email}")
            return json_error('Failed to send email. Please check SMTP configuration or try again later.', status=500)

    except Exception as e:
        logger.error(f"[FORGOT-PW] Unexpected error in send_password_reset_otp: {e}")
        import traceback
        traceback.print_exc()
        return json_error(f'Server error: {str(e)}', status=500)


@app.route('/api/forgot-password/verify-otp', methods=['POST'])
@rate_limit(calls=10, period=120)
def verify_password_reset_otp():
    """Verify OTP code."""
    try:
        logger.info("[FORGOT-PW] OTP verification request received")

        data = get_json_payload()
        if data is None:
            return json_error('Invalid JSON payload', status=400)

        email = session.get('reset_email', '')
        otp = data.get('otp', '').strip()

        if not email:
            return json_error('Session expired. Please start over.', status=400)
        if not otp or len(otp) != 6:
            return json_error('Please enter a valid 6-digit OTP', status=400)

        # Get the latest unused OTP for this email
        otp_record = db.execute_one(
            'SELECT * FROM password_reset_otp WHERE email = ? AND used = 0 ORDER BY created_at DESC LIMIT 1',
            (email,)
        )

        if not otp_record:
            return json_error('No active OTP found. Please request a new one.', status=400)

        # Check attempt limit (max 5)
        attempts = otp_record.get('attempts', 0) or 0
        if attempts >= 5:
            db.execute_update('UPDATE password_reset_otp SET used = 1 WHERE id = ?', (otp_record['id'],))
            return json_error('Too many attempts. Please request a new OTP.', status=429)

        # Check expiry
        try:
            expires_at = datetime.fromisoformat(str(otp_record['expires_at']))
            if datetime.now() > expires_at:
                db.execute_update('UPDATE password_reset_otp SET used = 1 WHERE id = ?', (otp_record['id'],))
                return json_error('OTP has expired. Please request a new one.', status=400)
        except (ValueError, TypeError):
            return json_error('OTP record invalid. Please request a new one.', status=400)

        # Increment attempt counter
        db.execute_update(
            'UPDATE password_reset_otp SET attempts = ? WHERE id = ?',
            (attempts + 1, otp_record['id'])
        )

        # Verify OTP hash
        if not email_service.verify_otp(otp_record['otp'], otp):
            remaining = 4 - attempts
            if remaining > 0:
                return json_error(f'Incorrect OTP. {remaining} attempt(s) remaining.', status=400)
            else:
                db.execute_update('UPDATE password_reset_otp SET used = 1 WHERE id = ?', (otp_record['id'],))
                return json_error('Too many failed attempts. Please request a new OTP.', status=429)

        # OTP verified — mark as used and set session flag
        db.execute_update('UPDATE password_reset_otp SET used = 1 WHERE id = ?', (otp_record['id'],))
        session['otp_verified'] = True
        logger.info(f"[FORGOT-PW] OTP verified for {email}")
        return json_success('OTP verified successfully')

    except Exception as e:
        logger.error(f"[FORGOT-PW] Unexpected error in verify_password_reset_otp: {e}")
        import traceback
        traceback.print_exc()
        return json_error(f'Server error: {str(e)}', status=500)


@app.route('/api/forgot-password/resend-otp', methods=['POST'])
@rate_limit(calls=3, period=120)
def resend_password_reset_otp():
    """Resend OTP with 60-second cooldown."""
    try:
        logger.info("[FORGOT-PW] Resend OTP request received")

        email = session.get('reset_email', '')
        if not email:
            return json_error('Session expired. Please start over.', status=400)

        # 60-second cooldown check
        last_otp = db.execute_one(
            'SELECT created_at FROM password_reset_otp WHERE email = ? ORDER BY created_at DESC LIMIT 1',
            (email,)
        )
        if last_otp:
            try:
                last_time = datetime.fromisoformat(str(last_otp['created_at']))
                elapsed = (datetime.now() - last_time).total_seconds()
                if elapsed < 60:
                    wait = int(60 - elapsed)
                    return json_error(f'Please wait {wait} seconds before resending', status=429)
            except (ValueError, TypeError):
                pass

        # Check user still exists
        user = db.execute_one('SELECT id FROM users WHERE email = ?', (email,))
        if not user:
            return json_error('Account not found', status=400)

        # Invalidate old OTPs
        db.execute_update(
            'UPDATE password_reset_otp SET used = 1 WHERE email = ? AND used = 0',
            (email,)
        )

        # Generate and store new OTP
        otp = email_service.generate_otp()
        otp_hash = email_service.hash_otp(otp)
        expires_at = email_service.get_otp_expiry()

        db.execute_insert(
            'INSERT INTO password_reset_otp (email, otp, expires_at, used, attempts) VALUES (?, ?, ?, 0, 0)',
            (email, otp_hash, expires_at)
        )
        logger.info(f"[FORGOT-PW] New OTP generated and stored for {email}")

        if email_service.send_otp_email(email, otp):
            session.pop('otp_verified', None)
            logger.info(f"[FORGOT-PW] Resent OTP to {email}")
            return json_success('New OTP sent to your email')
        else:
            logger.error(f"[FORGOT-PW] Failed to resend OTP email to {email}")
            return json_error('Failed to send email. Please try again later.', status=500)

    except Exception as e:
        logger.error(f"[FORGOT-PW] Unexpected error in resend_password_reset_otp: {e}")
        import traceback
        traceback.print_exc()
        return json_error(f'Server error: {str(e)}', status=500)


@app.route('/api/forgot-password/reset-password', methods=['POST'])
@rate_limit(calls=5, period=120)
def reset_password_submit():
    """Reset password after OTP verification."""
    try:
        logger.info("[FORGOT-PW] Password reset submission received")

        if not session.get('otp_verified'):
            return json_error('OTP not verified. Please verify your OTP first.', status=403)

        data = get_json_payload()
        if data is None:
            return json_error('Invalid JSON payload', status=400)

        email = session.get('reset_email', '')
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')

        if not email:
            return json_error('Session expired. Please start over.', status=400)

        if not new_password or not confirm_password:
            return json_error('Both password fields are required', status=400)

        if new_password != confirm_password:
            return json_error('Passwords do not match', status=400)

        is_valid, error_msg = validate_password(new_password)
        if not is_valid:
            return json_error(error_msg, status=400)

        # Update password
        password_hash = hash_password(new_password)
        db.execute_update('UPDATE users SET password_hash = ? WHERE email = ?', (password_hash, email))

        # Clear session
        session.pop('reset_email', None)
        session.pop('otp_verified', None)

        logger.info(f"[FORGOT-PW] Password reset successful for {email}")
        return json_success('Password reset successful! You can now log in with your new password.')

    except Exception as e:
        logger.error(f"[FORGOT-PW] Unexpected error in reset_password_submit: {e}")
        import traceback
        traceback.print_exc()
        return json_error(f'Server error: {str(e)}', status=500)


# ============================================================================
# DASHBOARD ROUTES
# ============================================================================

@app.route('/teacher/dashboard')
@login_required
@teacher_required
def teacher_dashboard():
    """Teacher dashboard page"""
    # CRITICAL: Verify role to prevent role-leak bug
    if session.get('role') != 'teacher':
        logger.warning(f"Unauthorized access attempt to teacher dashboard by user {get_current_user_id()} with role {session.get('role')}")
        session.clear()
        return redirect(url_for('login'))
    
    # Fetch teacher's classes
    classes = db.execute_query(
        '''SELECT c.*, 
           (SELECT COUNT(*) FROM enrollments WHERE class_id = c.id) as student_count,
           (SELECT COUNT(*) FROM lectures WHERE class_id = c.id) as lecture_count
           FROM classes c
           WHERE c.teacher_id = ?
           ORDER BY c.created_at DESC''',
        (get_current_user_id(),)
    )
    return render_template('teacher_dashboard.html', classes=classes)

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    """Student dashboard page"""
    # CRITICAL: Verify role to prevent role-leak bug
    if session.get('role') == 'teacher':
        logger.warning(f"Teacher {get_current_user_id()} attempted to access student dashboard")
        return redirect(url_for('teacher_dashboard'))
    
    # Fetch student's enrolled classes
    classes = db.execute_query(
        '''SELECT c.*, u.name as teacher_name,
           e.enrolled_at,
           COALESCE(
               (SELECT AVG(score * 100.0 / total) FROM quiz_submissions qs 
                JOIN quizzes q ON qs.quiz_id = q.id 
                WHERE q.class_id = c.id AND qs.student_id = ?), 0
           ) as progress
           FROM classes c
           JOIN enrollments e ON c.id = e.class_id
           JOIN users u ON c.teacher_id = u.id
           WHERE e.student_id = ?
           ORDER BY e.enrolled_at DESC''',
        (get_current_user_id(), get_current_user_id())
    )
    return render_template('student_dashboard.html', classes=classes)

# ============================================================================
# CLASS MANAGEMENT ROUTES
# ============================================================================

@app.route('/api/teacher/classes')
@api_login_required
@api_teacher_required
def get_teacher_classes():
    """Get all classes for logged-in teacher"""
    classes = db.execute_query(
        '''SELECT c.*, 
           (SELECT COUNT(*) FROM enrollments WHERE class_id = c.id) as student_count
           FROM classes c
           WHERE c.teacher_id = ?
           ORDER BY c.created_at DESC''',
        (get_current_user_id(),)
    )
    return jsonify(classes)

@app.route('/api/create_class', methods=['POST'])
@api_login_required
@api_teacher_required
def create_class():
    """Create a new class"""
    try:
        data = request.get_json(silent=True)
        if not data:
            return json_error('Invalid JSON payload', status=400)
        
        title = sanitize_input(data.get('title', ''))
        description = sanitize_input(data.get('description', ''), max_length=2000)
        
        if not title:
            return json_error('Title is required', status=400)
        
        # Generate unique class code
        class_code = generate_class_code()
        
        # Ensure code uniqueness
        while db.execute_one('SELECT id FROM classes WHERE code = ?', (class_code,)):
            class_code = generate_class_code()

        class_id = db.execute_insert(
            'INSERT INTO classes (title, description, teacher_id, code) VALUES (?, ?, ?, ?)',
            (title, description, get_current_user_id(), class_code)
        )
        
        logger.info(f"Class created: {title} (ID: {class_id})")
        return json_success('Class created', data={'class_id': class_id, 'code': class_code}, status=201, class_id=class_id)
    except Exception as e:
        logger.error(f"Error creating class: {e}")
        return json_error(f'Failed to create class: {str(e)}', status=500)

@app.route('/api/student/classes')
@api_login_required
def get_student_classes():
    """Get enrolled classes for logged-in student"""
    classes = db.execute_query(
        '''SELECT c.*, u.name as teacher_name
           FROM classes c
           JOIN enrollments e ON c.id = e.class_id
           JOIN users u ON c.teacher_id = u.id
           WHERE e.student_id = ?
           ORDER BY e.enrolled_at DESC''',
        (get_current_user_id(),)
    )
    return jsonify(classes)



@app.route('/api/user/data')
@api_login_required
def get_user_data():
    """Get user data with enrolled classes for student dashboard"""
    # Get user information
    user = db.execute_one('SELECT name, email FROM users WHERE id = ?', (get_current_user_id(),))
    
    if session.get('role') == 'student':
        classes = db.execute_query(
            '''SELECT c.*, u.name as teacher,
               COALESCE(
                   (SELECT AVG(score * 100.0 / total) FROM quiz_submissions qs 
                    JOIN quizzes q ON qs.quiz_id = q.id 
                    WHERE q.class_id = c.id AND qs.student_id = ?), 0
               ) as progress
               FROM classes c
               JOIN enrollments e ON c.id = e.class_id
               JOIN users u ON c.teacher_id = u.id
               WHERE e.student_id = ?
               ORDER BY e.enrolled_at DESC''',
            (get_current_user_id(), get_current_user_id())
        )
        return jsonify({
            'classes': classes,
            'name': user['name'] if user else '',
            'email': user['email'] if user else ''
        })
    
    return jsonify({
        'classes': [],
        'name': user['name'] if user else '',
        'email': user['email'] if user else ''
    })


@app.route('/api/browse_classes')
@api_login_required
def browse_classes():
    """Get all available classes for browsing"""
    classes = db.execute_query(
        '''SELECT c.*, u.name as teacher, u.name as instructor,
           (SELECT COUNT(*) FROM enrollments WHERE class_id = c.id) as student_count
           FROM classes c
           JOIN users u ON c.teacher_id = u.id
           ORDER BY c.created_at DESC''',
    )
    return jsonify(classes)

@app.route('/api/teacher/students')
@api_login_required
@api_teacher_required
def get_teacher_students():
    """Get all students enrolled in teacher's classes"""
    students = db.execute_query(
        '''SELECT DISTINCT u.id, u.name, u.email,
           (SELECT COUNT(*) FROM quiz_submissions qs 
            JOIN quizzes q ON qs.quiz_id = q.id 
            JOIN classes c ON q.class_id = c.id
            WHERE qs.student_id = u.id AND c.teacher_id = ?) as quizzes_taken
           FROM users u
           JOIN enrollments e ON u.id = e.student_id
           JOIN classes c ON e.class_id = c.id
           WHERE c.teacher_id = ?
           ORDER BY u.name''',
        (get_current_user_id(), get_current_user_id())
    )
    return jsonify(students)


@app.route('/api/teacher/alerts')
@api_login_required
@api_teacher_required
def get_teacher_alerts():
    """Get intervention alerts for teacher dashboard."""
    teacher_id = get_current_user_id()

    if table_exists('teacher_interventions'):
        alerts = db.execute_query(
            '''SELECT ti.id, ti.alert_type, ti.message, ti.is_resolved, ti.created_at,
                      u.name as student_name, c.title as class_title
               FROM teacher_interventions ti
               JOIN users u ON ti.student_id = u.id
               JOIN classes c ON ti.class_id = c.id
               WHERE ti.teacher_id = ?
               ORDER BY ti.is_resolved ASC, ti.created_at DESC
               LIMIT 50''',
            (teacher_id,)
        )
        return json_success(message='Alerts loaded', data={'alerts': alerts}, alerts=alerts)

    # Fallback generated alerts from current performance
    generated_alerts = db.execute_query(
        '''SELECT u.name as student_name, c.title as class_title,
                  ROUND(COALESCE(AVG(qs.score * 100.0 / NULLIF(qs.total, 0)), 0), 1) as avg_score,
                  MAX(qs.submitted_at) as last_attempt
           FROM enrollments e
           JOIN users u ON e.student_id = u.id
           JOIN classes c ON e.class_id = c.id
           LEFT JOIN quizzes q ON q.class_id = c.id
           LEFT JOIN quiz_submissions qs ON qs.quiz_id = q.id AND qs.student_id = e.student_id
           WHERE c.teacher_id = ?
           GROUP BY u.id, c.id
           HAVING avg_score > 0 AND avg_score < 65
           ORDER BY avg_score ASC
           LIMIT 20''',
        (teacher_id,)
    )
    alerts = [{
        'id': f"generated-{idx}",
        'alert_type': 'low_performance',
        'message': f"{row['student_name']} is below target ({row['avg_score']}%). Consider intervention.",
        'is_resolved': 0,
        'created_at': row['last_attempt'],
        'student_name': row['student_name'],
        'class_title': row['class_title']
    } for idx, row in enumerate(generated_alerts, start=1)]
    return json_success(message='Alerts loaded', data={'alerts': alerts}, alerts=alerts)


@app.route('/api/teacher/feedback')
@api_login_required
@api_teacher_required
def get_teacher_feedback():
    """Get learner feedback entries for teacher dashboard."""
    teacher_id = get_current_user_id()

    if table_exists('feedback'):
        feedback_items = db.execute_query(
            '''SELECT f.id, f.rating, f.message, f.created_at, u.name as student_name
               FROM feedback f
               JOIN users u ON f.user_id = u.id
               JOIN enrollments e ON e.student_id = u.id
               JOIN classes c ON c.id = e.class_id
               WHERE c.teacher_id = ?
               GROUP BY f.id
               ORDER BY f.created_at DESC
               LIMIT 50''',
            (teacher_id,)
        )
        return json_success(message='Feedback loaded', data={'feedback': feedback_items}, feedback=feedback_items)

    # Fallback: synthesize from recent submissions so tab has meaningful data
    feedback_items = db.execute_query(
        '''SELECT u.name as student_name, q.title as quiz_title,
                  ROUND(qs.score * 100.0 / NULLIF(qs.total, 0), 1) as score_percent,
                  qs.submitted_at as created_at
           FROM quiz_submissions qs
           JOIN users u ON u.id = qs.student_id
           JOIN quizzes q ON q.id = qs.quiz_id
           JOIN classes c ON c.id = q.class_id
           WHERE c.teacher_id = ?
           ORDER BY qs.submitted_at DESC
           LIMIT 20''',
        (teacher_id,)
    )
    normalized = [{
        'id': f"derived-{idx}",
        'rating': 5 if row['score_percent'] >= 80 else (4 if row['score_percent'] >= 65 else 3),
        'message': f"Recent {row['quiz_title']} score: {row['score_percent']}%",
        'created_at': row['created_at'],
        'student_name': row['student_name']
    } for idx, row in enumerate(feedback_items, start=1)]
    return json_success(message='Feedback loaded', data={'feedback': normalized}, feedback=normalized)

@app.route('/api/student/analytics')
@api_login_required
def get_student_analytics():
    """Get analytics for the current student"""
    try:
        student_id = get_current_user_id()
        
        # Overall Stats
        stats = db.execute_one(
            '''SELECT 
                COUNT(*) as total_completed,
                COALESCE(SUM(score), 0) as total_correct,
                COALESCE(SUM(total), 0) as total_questions,
                COALESCE(AVG(CAST(score AS FLOAT) / NULLIF(total, 0) * 100), 0) as avg_score
               FROM quiz_submissions 
               WHERE student_id = ?''',
            (student_id,)
        )
        
        # Total available quizzes (to calculate progress)
        total_available = db.execute_one(
            '''SELECT COUNT(DISTINCT q.id) as count
               FROM quizzes q
               JOIN enrollments e ON q.class_id = e.class_id
               WHERE e.student_id = ?''',
            (student_id,)
        )['count']
        
        overall_progress = round((stats['total_completed'] / total_available * 100) if total_available > 0 else 0)
        accuracy = round((stats['total_correct'] / stats['total_questions'] * 100) if stats['total_questions'] > 0 else 0)
        avg_score = round(stats['avg_score'])
        
        # Weekly Trend (Last 7 Days)
        weekly_data = db.execute_query(
            '''SELECT DATE(submitted_at) as date, 
                      AVG(CAST(score AS FLOAT) / NULLIF(total, 0) * 100) as score
               FROM quiz_submissions 
               WHERE student_id = ? AND submitted_at >= DATE('now', '-7 days')
               GROUP BY DATE(submitted_at)
               ORDER BY date''',
            (student_id,)
        )
        weekly_trend = [{'day': item['date'], 'score': round(item['score'])} for item in weekly_data]
        weekly_activity = {
            'labels': [item['date'] for item in weekly_data],
            'data': [round(item['score']) for item in weekly_data]
        }
        
        # Topic Breakdown (Using Quiz Titles as Topics)
        topic_data = db.execute_query(
            '''SELECT q.title as topic, 
                      AVG(CAST(qs.score AS FLOAT) / NULLIF(qs.total, 0) * 100) as score
               FROM quiz_submissions qs
               JOIN quizzes q ON qs.quiz_id = q.id
               WHERE qs.student_id = ?
               GROUP BY q.title
               ORDER BY score DESC''',
            (student_id,)
        )
        
        topic_breakdown = [{'topic': item['topic'], 'score': round(item['score'])} for item in topic_data]
        strong_topics = topic_breakdown[:3]
        weak_topics = sorted(topic_breakdown, key=lambda x: x['score'])[:3]
        
        # Recent Quiz Attempts
        recent_attempts_data = db.execute_query(
            '''SELECT q.title as quiz_title, c.title as class_name, c.id as class_id,
                      qs.score as correct_answers, qs.total as total_questions,
                      qs.submitted_at, qs.duration_seconds
               FROM quiz_submissions qs
               JOIN quizzes q ON qs.quiz_id = q.id
               JOIN classes c ON q.class_id = c.id
               WHERE qs.student_id = ?
               ORDER BY qs.submitted_at DESC
               LIMIT 10''',
            (student_id,)
        )
        
        quiz_attempts = []
        for attempt in recent_attempts_data:
            score_percent = round((attempt['correct_answers'] / attempt['total_questions'] * 100) if attempt['total_questions'] > 0 else 0)
            quiz_attempts.append({
                'quiz_title': attempt['quiz_title'],
                'class_name': attempt['class_name'],
                'class_id': attempt['class_id'],
                'correct_answers': attempt['correct_answers'],
                'total_questions': attempt['total_questions'],
                'score_percent': score_percent,
                'submitted_at': attempt['submitted_at'],
                'time_taken_minutes': round((attempt['duration_seconds'] or 0) / 60, 1),
                'difficulty': 'Medium' # Placeholder
            })

        # Subject-wise Progress
        subjects = db.execute_query(
            '''SELECT c.id, c.title, c.description 
               FROM classes c
               JOIN enrollments e ON c.id = e.class_id
               WHERE e.student_id = ?''',
            (student_id,)
        )
        
        subject_progress = []
        for subj in subjects:
            # Count modules
            total_mods = db.execute_one('SELECT COUNT(*) as count FROM learning_modules WHERE class_id = ?', (subj['id'],))['count']
            
            # Count completed (via progress table)
            completed_mods = db.execute_one(
                '''SELECT COUNT(*) as count FROM student_module_progress 
                   WHERE user_id = ? AND module_id IN (SELECT id FROM learning_modules WHERE class_id = ?) 
                   AND status = 'COMPLETED' ''',
                (student_id, subj['id'])
            )['count']
            
            progress_pct = round((completed_mods / total_mods * 100) if total_mods > 0 else 0)
            subject_progress.append({
                'id': subj['id'],
                'title': subj['title'],
                'percent': progress_pct,
                'total_modules': total_mods,
                'completed_modules': completed_mods
            })
            
        return jsonify({
            'overall_progress': overall_progress,
            'avg_score': avg_score,
            'total_quizzes': stats['total_completed'],
            'accuracy': accuracy,
            'weekly_trend': weekly_trend,
            'weekly_activity': weekly_activity,
            'topic_breakdown': topic_breakdown,
            'strong_topics': strong_topics,
            'weak_topics': weak_topics,
            'quiz_attempts': quiz_attempts,
            'subject_progress': subject_progress
        })

    except Exception as e:
        logger.error(f"Error fetching student analytics: {e}")
        return jsonify({'error': 'Failed to load analytics'}), 500



@app.route('/api/exam-prediction')
@api_login_required
def get_exam_prediction():
    """Get the latest exam prediction for the current student."""
    try:
        student_id = get_current_user_id()
        prediction = exam_predictor.get_latest_prediction(student_id)
        return json_success(data=prediction)
    except Exception as e:
        logger.error(f"Error fetching exam prediction: {e}")
        return json_error('Failed to load prediction', status=500)


@app.route('/api/leaderboard/<int:class_id>')
@api_login_required
def get_class_leaderboard(class_id):
    """Get leaderboard for a specific class."""
    try:
        data = leaderboard_engine.get_class_leaderboard(class_id, limit=10)
        return json_success(data)
    except Exception as e:
        logger.error(f"Error fetching class leaderboard: {e}")
        return json_error("Failed to fetch leaderboard", 500)


@app.route('/api/leaderboard/global')
@api_login_required
@api_teacher_required
def get_global_leaderboard():
    """Get global leaderboard for teacher analytics."""
    try:
        data = leaderboard_engine.get_global_leaderboard(limit=10)
        return json_success(data)
    except Exception as e:
        logger.error(f"Error fetching global leaderboard: {e}")
        return json_error("Failed to fetch global leaderboard", 500)


@app.route('/api/teacher/analytics')
@api_login_required
@api_teacher_required
def get_teacher_analytics():
    """Get overview analytics for all teacher's classes"""
    try:
        teacher_id = get_current_user_id()
        logger.info(f"Fetching analytics for teacher {teacher_id}")
        
        # Get all classes with basic stats
        classes = db.execute_query(
            '''SELECT c.id as class_id, c.title as class_name,
               (SELECT COUNT(*) FROM enrollments WHERE class_id = c.id) as total_students,
               COALESCE((SELECT AVG(qs.score) 
                FROM quiz_submissions qs 
                JOIN quizzes q ON qs.quiz_id = q.id 
                WHERE q.class_id = c.id), 0) as avg_class_score
               FROM classes c
               WHERE c.teacher_id = ?
               ORDER BY c.created_at DESC''',
            (teacher_id,)
        )
        
        return jsonify({
            'success': True,
            'class_analytics': classes
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching teacher analytics: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load analytics',
            'class_analytics': []
        }), 500

@app.route('/api/teacher/class-stats/<int:class_id>')
@api_login_required
@api_teacher_required
def get_class_stats(class_id):
    """Get detailed analytics for a specific class"""
    try:
        teacher_id = get_current_user_id()
        
        # Verify teacher owns this class
        class_check = db.execute_one(
            'SELECT id FROM classes WHERE id = ? AND teacher_id = ?',
            (class_id, teacher_id)
        )
        
        if not class_check:
            return jsonify({'error': 'Unauthorized'}), 403
        
        logger.info(f"Fetching stats for class {class_id}")
        
        # Total students
        total_students = db.execute_one(
            'SELECT COUNT(*) as count FROM enrollments WHERE class_id = ?',
            (class_id,)
        )['count']
        
        # Active students today
        active_today = db.execute_one(
            '''SELECT COUNT(DISTINCT qs.student_id) as count
               FROM quiz_submissions qs
               JOIN quizzes q ON qs.quiz_id = q.id
               WHERE q.class_id = ? AND DATE(qs.submitted_at) = DATE('now')''',
            (class_id,)
        )['count']
        
        # Average class score
        avg_score_result = db.execute_one(
            '''SELECT COALESCE(AVG(qs.score), 0) as avg_score
               FROM quiz_submissions qs
               JOIN quizzes q ON qs.quiz_id = q.id
               WHERE q.class_id = ?''',
            (class_id,)
        )
        avg_class_score = round(avg_score_result['avg_score'] if avg_score_result else 0)
        
        # Quiz completion rate
        total_quizzes = db.execute_one(
            'SELECT COUNT(*) as count FROM quizzes WHERE class_id = ?',
            (class_id,)
        )['count']
        
        completed_submissions = db.execute_one(
            '''SELECT COUNT(*) as count FROM quiz_submissions qs
               JOIN quizzes q ON qs.quiz_id = q.id
               WHERE q.class_id = ?''',
            (class_id,)
        )['count']
        
        total_possible = total_quizzes * total_students if total_students > 0 else 1
        completion_rate = round((completed_submissions / total_possible) * 100) if total_possible > 0 else 0
        
        # Performance distribution
        distribution_data = db.execute_query(
            '''SELECT 
                CASE 
                    WHEN qs.score >= 90 THEN 'A (90-100)'
                    WHEN qs.score >= 80 THEN 'B (80-89)'
                    WHEN qs.score >= 70 THEN 'C (70-79)'
                    WHEN qs.score >= 60 THEN 'D (60-69)'
                    ELSE 'F (0-59)'
                END as grade,
                COUNT(*) as count
               FROM quiz_submissions qs
               JOIN quizzes q ON qs.quiz_id = q.id
               WHERE q.class_id = ?
               GROUP BY grade
               ORDER BY grade''',
            (class_id,)
        )
        
        performance_distribution = {item['grade']: item['count'] for item in distribution_data}
        
        # Ensure all grades exist
        for grade in ['A (90-100)', 'B (80-89)', 'C (70-79)', 'D (60-69)', 'F (0-59)']:
            if grade not in performance_distribution:
                performance_distribution[grade] = 0
        
        # Participation trend (last 7 days)
        participation_data = db.execute_query(
            '''SELECT DATE(qs.submitted_at) as date, COUNT(*) as count
               FROM quiz_submissions qs
               JOIN quizzes q ON qs.quiz_id = q.id
               WHERE q.class_id = ? AND DATE(qs.submitted_at) >= DATE('now', '-7 days')
               GROUP BY DATE(qs.submitted_at)
               ORDER BY date''',
            (class_id,)
        )
        
        participation_trend = [{'date': item['date'], 'count': item['count']} for item in participation_data]
        
        # Most difficult quiz
        difficult_quiz = db.execute_one(
            '''SELECT q.title as title, COALESCE(AVG(qs.score), 0) as avg_score, COUNT(qs.id) as attempts
               FROM quizzes q
               LEFT JOIN quiz_submissions qs ON q.id = qs.quiz_id
               WHERE q.class_id = ?
               GROUP BY q.id
               HAVING COUNT(qs.id) > 0
               ORDER BY avg_score ASC
               LIMIT 1''',
            (class_id,)
        )
        
        if not difficult_quiz:
            difficult_quiz = {'title': 'No quizzes yet', 'avg_score': 0, 'attempts': 0}
        else:
            difficult_quiz['avg_score'] = round(difficult_quiz['avg_score'])
        
        # Most failed topic (extract from quiz names)
        failed_topic = "No data available"
        
        # Top students
        top_students_data = db.execute_query(
            '''SELECT u.name, COALESCE(AVG(qs.score), 0) as avg_score, COUNT(qs.id) as quizzes_completed
               FROM users u
               JOIN enrollments e ON u.id = e.student_id
               LEFT JOIN quiz_submissions qs ON u.id = qs.student_id
               LEFT JOIN quizzes q ON qs.quiz_id = q.id AND q.class_id = ?
               WHERE e.class_id = ?
               GROUP BY u.id
               HAVING COUNT(qs.id) > 0
               ORDER BY avg_score DESC
               LIMIT 5''',
            (class_id, class_id)
        )
        
        top_students = []
        for idx, student in enumerate(top_students_data):
            top_students.append({
                'rank': idx + 1,
                'name': student['name'],
                'avg_score': round(student['avg_score']),
                'quizzes_completed': student['quizzes_completed']
            })
        
        return jsonify({
            'total_students': total_students,
            'active_students_today': active_today,
            'avg_class_score': avg_class_score,
            'quiz_completion_rate': completion_rate,
            'performance_distribution': performance_distribution,
            'completion_stats': {
                'completed': completed_submissions,
                'pending': total_possible - completed_submissions
            },
            'participation_trend': participation_trend,
            'most_difficult_quiz': difficult_quiz,
            'most_failed_topic': failed_topic,
            'top_students': top_students
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching class stats: {e}")
        return jsonify({'error': 'Failed to load class stats'}), 500


@app.route('/api/join_class', methods=['POST'])
@api_login_required
def join_class():
    """Enroll student in a class using code"""
    data = get_json_payload()
    if data is None:
        return json_error('Invalid JSON payload', status=400)
    
    code = data.get('code')
    
    if not code:
        return json_error('Class Code is required', status=400)

    # Find class by code
    class_info = db.execute_one('SELECT id, title FROM classes WHERE code = ?', (code,))
    
    if not class_info:
        return json_error('Invalid Class Code', status=404)
    
    class_id = class_info['id']
    
    # Check if already enrolled
    existing = db.execute_one(
        'SELECT id FROM enrollments WHERE student_id = ? AND class_id = ?',
        (get_current_user_id(), class_id)
    )
    
    if existing:
        return json_error('Already enrolled in this class', status=400)
    
    db.execute_insert(
        'INSERT INTO enrollments (student_id, class_id) VALUES (?, ?)',
        (get_current_user_id(), class_id)
    )
    
    logger.info(f"Student {get_current_user_id()} enrolled in class {class_id} via code {code}")
    return json_success(f"Successfully joined {class_info['title']}", status=201)

@app.route('/api/leave_class', methods=['POST'])
@api_login_required
def leave_class():
    """Unenroll student from a class"""
    data = get_json_payload()
    class_id = data.get('class_id')
    
    if not class_id:
        return json_error('Class ID required', status=400)
        
    try:
        class_id = int(class_id)
    except:
        return json_error('Invalid Class ID', status=400)

    # Verify enrollment exists
    existing = db.execute_one(
        'SELECT id FROM enrollments WHERE student_id = ? AND class_id = ?',
        (get_current_user_id(), class_id)
    )
    
    if not existing:
        return json_error('Not enrolled in this class', status=404)

    # Allow leaving
    db.execute_update(
        'DELETE FROM enrollments WHERE student_id = ? AND class_id = ?',
        (get_current_user_id(), class_id)
    )
    
    logger.info(f"Student {get_current_user_id()} left class {class_id}")
    return json_success('Successfully left the class')

@app.route('/api/student/recommendations/legacy')
@api_login_required
def get_student_recommendations_legacy():
    """Get AI-powered recommendations for student"""
    # TODO: Implement real AI recommendations based on student performance
    # For now, return empty array so frontend shows empty state
    try:
        logger.info(f"Fetching recommendations for student {get_current_user_id()}")
        # Placeholder implementation - return empty recommendations
        return jsonify({
            'success': True,
            'recommendations': []
        }), 200
    except Exception as e:
        logger.error(f"Error fetching recommendations: {e}")
        return jsonify({'success': False, 'error': 'Failed to load recommendations', 'recommendations': []}), 500

@app.route('/api/student/knowledge-gaps/legacy')
@api_login_required
def get_knowledge_gaps_legacy():
    """Get knowledge gap analysis for student"""
    # TODO: Implement real knowledge gap analysis based on quiz performance
    # For now, return empty array so frontend shows empty state
    try:
        logger.info(f"Fetching knowledge gaps for student {get_current_user_id()}")
        # Placeholder implementation - return empty gaps
        return jsonify({
            'success': True,
            'gaps': []
        }), 200
    except Exception as e:
        logger.error(f"Error fetching knowledge gaps: {e}")
        return jsonify({'success': False, 'error': 'Failed to load knowledge gaps', 'gaps': []}), 500

@app.route('/class/<int:class_id>')
@login_required
def class_view(class_id):
    """Class view page"""
    # Get class details with teacher name
    class_info = db.execute_one('''
        SELECT c.*, u.name as teacher_name 
        FROM classes c 
        JOIN users u ON c.teacher_id = u.id 
        WHERE c.id = ?
    ''', (class_id,))
    
    if not class_info:
        return "Class not found", 404
    
    # Check access
    if session['role'] == 'student':
        enrollment = db.execute_one(
            'SELECT id FROM enrollments WHERE student_id = ? AND class_id = ?',
            (get_current_user_id(), class_id)
        )
        if not enrollment:
            return "Access denied", 403
    elif class_info['teacher_id'] != get_current_user_id():
        return "Access denied", 403
    
    # Get lectures
    lectures = db.execute_query(
        'SELECT * FROM lectures WHERE class_id = ? ORDER BY uploaded_at DESC',
        (class_id,)
    )
    
    # Get quizzes
    quizzes = db.execute_query(
        '''SELECT q.*, 
           (SELECT COUNT(*) FROM quiz_questions WHERE quiz_id = q.id) as question_count
           FROM quizzes q
           WHERE q.class_id = ?
           ORDER BY q.created_at DESC''',
        (class_id,)
    )
    
    # Check for active live session
    active_session = db.execute_one(
        'SELECT * FROM live_sessions WHERE class_id = ? AND is_active = 1',
        (class_id,)
    )
    
    # Get progress for student
    if session['role'] == 'student':
        progress_data = db.execute_one(
            'SELECT * FROM student_metrics WHERE user_id = ? AND class_id = ?',
            (get_current_user_id(), class_id)
        )
        progress = progress_data['rating'] if progress_data else 0
    else:
        progress = 0
    
    return render_template('class_view.html', 
                         class_id=class_id, 
                         class_info=class_info, 
                         lectures=lectures,
                         quizzes=quizzes,
                         active_session=active_session,
                         progress=progress)


@app.route('/api/generate-adaptive-quiz', methods=['POST'])
@api_login_required
@rate_limit(calls=3, period=120)
def generate_adaptive_quiz():
    """Generate an AI-powered adaptive quiz for the student."""
    if session.get('role') != 'student':
        return json_error('Only students can generate adaptive quizzes', status=403)

    data = get_json_payload()
    if data is None:
        return json_error('Invalid JSON payload', status=400)

    class_id = data.get('class_id')
    if not class_id:
        return json_error('class_id is required', status=400)

    try:
        class_id = int(class_id)
    except (TypeError, ValueError):
        return json_error('Invalid class_id', status=400)

    student_id = get_current_user_id()

    # Verify enrollment
    enrollment = db.execute_one(
        'SELECT id FROM enrollments WHERE student_id = ? AND class_id = ?',
        (student_id, class_id)
    )
    if not enrollment:
        return json_error('You are not enrolled in this class', status=403)

    # Get class title
    class_info = db.execute_one('SELECT title FROM classes WHERE id = ?', (class_id,))
    if not class_info:
        return json_error('Class not found', status=404)

    try:
        result = adaptive_quiz.generate_quiz(student_id, class_id, class_info['title'])
        return json_success(
            message='Adaptive quiz generated successfully',
            data=result
        )
    except Exception as e:
        logger.exception('Failed to generate adaptive quiz')
        return json_error('Failed to generate quiz', status=500)


@app.route('/api/class/<int:class_id>')
@login_required
def get_class_data(class_id):
    """Get class details API"""
    class_info = db.execute_one('SELECT * FROM classes WHERE id = ?', (class_id,))
    
    if not class_info:
        return jsonify({'error': 'Class not found'}), 404
    
    # Check access
    if session['role'] == 'student':
        enrollment = db.execute_one(
            'SELECT id FROM enrollments WHERE student_id = ? AND class_id = ?',
            (get_current_user_id(), class_id)
        )
        if not enrollment:
            return jsonify({'error': 'Access denied'}), 403
    elif class_info['teacher_id'] != get_current_user_id():
        return jsonify({'error': 'Access denied'}), 403
    
    # Get student count
    student_count = db.execute_one(
        'SELECT COUNT(*) as count FROM enrollments WHERE class_id = ?',
        (class_id,)
    )['count']
    
    # Get teacher info
    teacher = db.execute_one(
        'SELECT name FROM users WHERE id = ?',
        (class_info['teacher_id'],)
    )
    
    result = dict(class_info)
    result['student_count'] = student_count
    result['teacher_name'] = teacher['name'] if teacher else 'Unknown'
    
    return jsonify(result)

# ============================================================================
# CONTENT MANAGEMENT ROUTES
# ============================================================================

@app.route('/api/upload_lecture', methods=['POST'])
@login_required
@teacher_required
def upload_lecture():
    """Upload lecture file with robust error handling"""
    try:
        if 'file' not in request.files:
            return json_error('No file provided', status=400)
        
        file = request.files['file']
        class_id = request.form.get('class_id')
        
        if file.filename == '':
            return json_error('No file selected', status=400)
        
        # Validate file type
        allowed_extensions = {'pdf', 'ppt', 'pptx', 'doc', 'docx', 'txt', 'mp4', 'mp3'}
        if not validate_file_type(file.filename, allowed_extensions):
            return json_error('Invalid file type. Allowed: pdf, ppt, doc, txt, mp4, mp3', status=400)
        
        if file and class_id:
            filename = secure_filename(file.filename)
            
            # Ensure upload directory exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Save file
            try:
                file.save(filepath)
            except Exception as e:
                logger.error(f"File save failed: {e}")
                return json_error(f"Failed to save file: {str(e)}", status=500)
            
            file_size = os.path.getsize(filepath)
            
            # DB Insert
            try:
                lecture_id = db.execute_insert(
                    'INSERT INTO lectures (class_id, filename, filepath, file_size) VALUES (?, ?, ?, ?)',
                    (class_id, filename, filepath, file_size)
                )
                logger.info(f"Lecture uploaded: {filename} (ID: {lecture_id}, Class: {class_id})")
                return jsonify({
                    'success': True, 
                    'message': 'Lecture uploaded successfully', 
                    'data': {'filename': filename, 'id': lecture_id}
                }), 201
            except Exception as e:
                # If DB fails, try to delete the uploaded file to avoid orphans
                try:
                    os.remove(filepath)
                except:
                    pass
                logger.error(f"Database insert failed: {e}")
                import traceback
                traceback.print_exc()
                return json_error(f"Database error: {str(e)}", status=500)

        return json_error('Invalid request data', status=400)
        
    except Exception as e:
        logger.exception("Unexpected error in upload_lecture")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'Internal Server Error',
            'error': str(e)
        }), 500

@app.route('/api/class/<int:class_id>/lectures')
@login_required
def get_class_lectures(class_id):
    """Get all lectures for a class"""
    lectures = db.execute_query(
        'SELECT * FROM lectures WHERE class_id = ? ORDER BY uploaded_at DESC',
        (class_id,)
    )
    return jsonify(lectures)

@app.route('/api/create_quiz', methods=['POST'])
@login_required
@teacher_required
def create_quiz():
    """Create a new quiz"""
    data = get_json_payload()
    if data is None:
        return json_error('Invalid JSON payload', status=400)
    
    # Validate quiz data
    is_valid, error_msg = validate_quiz_data(data)
    if not is_valid:
        return json_error(error_msg, status=400)
    
    class_id = data.get('class_id')
    title = sanitize_input(data.get('title', ''))
    description = sanitize_input(data.get('description', ''), max_length=2000)
    questions = data.get('questions', [])
    
    # Create quiz
    quiz_id = db.execute_insert(
        'INSERT INTO quizzes (class_id, title, description) VALUES (?, ?, ?)',
        (class_id, title, description)
    )
    
    # Add questions
    with db.get_db() as conn:
        for q in questions:
            conn.execute(
                'INSERT INTO quiz_questions (quiz_id, question_text, options, correct_option_index, explanation) VALUES (?, ?, ?, ?, ?)',
                (quiz_id, q['question'], json.dumps(q['options']), q['correct'], q.get('explanation', ''))
            )
    
    logger.info(f"Quiz created: {title} (ID: {quiz_id}, Questions: {len(questions)})")
    return json_success('Quiz created', data={'quiz_id': quiz_id}, status=201, quiz_id=quiz_id)

@app.route('/api/class/<int:class_id>/quizzes')
@api_login_required
def get_class_quizzes(class_id):
    """Get all quizzes for a class"""
    quizzes = db.execute_query(
        '''SELECT q.*, 
           (SELECT COUNT(*) FROM quiz_questions WHERE quiz_id = q.id) as question_count
           FROM quizzes q
           WHERE q.class_id = ?
           ORDER BY q.created_at DESC''',
        (class_id,)
    )
    return jsonify(quizzes)

@app.route('/quiz/<int:quiz_id>')
@login_required
def quiz_page(quiz_id):
    """Render the quiz-taking page."""
    quiz = db.execute_one('SELECT * FROM quizzes WHERE id = ?', (quiz_id,))
    if not quiz:
        return 'Quiz not found', 404
    return render_template('quiz_view.html', quiz_id=quiz_id)

@app.route('/api/quiz/<int:quiz_id>')
@api_login_required
def get_quiz(quiz_id):
    """Get quiz details with questions"""
    quiz = db.execute_one('SELECT * FROM quizzes WHERE id = ?', (quiz_id,))
    if not quiz:
        return jsonify({'success': False, 'error': 'Quiz not found', 'message': 'Quiz not found'}), 404
    
    questions = db.execute_query(
        'SELECT id, question_text, options, explanation FROM quiz_questions WHERE quiz_id = ?',
        (quiz_id,)
    )
    
    quiz_data = dict(quiz)
    
    # Check attempts
    user_id = get_current_user_id()
    role = session.get('role')
    
    attempts_taken = 0
    max_attempts = 3
    is_allowed = True
    can_view_results = False

    if role == 'student':
        attempts = db.execute_one(
            'SELECT COUNT(*) as count FROM quiz_submissions WHERE quiz_id = ? AND student_id = ?',
            (quiz_id, user_id)
        )
        attempts_taken = attempts['count']
        if attempts_taken >= max_attempts:
            is_allowed = False
            can_view_results = True
            
    quiz_data['attempts_taken'] = attempts_taken
    quiz_data['max_attempts'] = max_attempts
    quiz_data['is_allowed'] = is_allowed
    quiz_data['can_view_results'] = can_view_results

    # Fetch Questions
    questions = db.execute_query(
        'SELECT id, question_text, options, explanation FROM quiz_questions WHERE quiz_id = ?',
        (quiz_id,)
    )

    quiz_data['questions'] = questions
    for q in quiz_data['questions']:
        try:
            q['options'] = json.loads(q.get('options') or '[]')
        except Exception:
            q['options'] = []
        # SECURITY: Strip explanation until attempt 3+
        # attempts_taken < 2 means this will be attempt 1 or 2 → hide explanation
        if attempts_taken < 2:
            q.pop('explanation', None)
    
    return jsonify({'success': True, 'data': quiz_data}), 200

@app.route('/api/submit_quiz', methods=['POST'])
@api_login_required
@rate_limit(calls=8, period=60)
def submit_quiz():
    """Legacy submit endpoint kept for compatibility - delegates to handler."""
    data = get_json_payload()
    if data is None:
        return json_error('Invalid JSON payload', status=400)
    return _handle_quiz_submission(data, get_current_user_id())


def _handle_quiz_submission(data, user_id):
    """Shared handler for quiz submission logic. Returns (Response, status)."""
    try:
        logger.info("[SUBMIT_QUIZ] Starting submission for user %s", user_id)

        if session.get('role') != 'student':
            return json_error('Only students can submit quizzes', status=403)

        quiz_id = data.get('quiz_id')
        answers = data.get('answers', {}) or {}
        duration = data.get('duration', 0)

        if not quiz_id:
            return json_error('Quiz ID required', status=400)

        try:
            quiz_id = int(quiz_id)
        except (TypeError, ValueError):
            return json_error('Invalid quiz_id', status=400)

        if not isinstance(answers, dict):
            return json_error('Invalid answers payload', status=400)

        try:
            duration = int(duration or 0)
            if duration < 0:
                duration = 0
        except (TypeError, ValueError):
            duration = 0

        quiz = db.execute_one('SELECT id, class_id FROM quizzes WHERE id = ?', (quiz_id,))
        if not quiz:
            return json_error('Quiz not found', status=404)

        # Verify enrollment for students
        enrollment = db.execute_one(
            'SELECT id FROM enrollments WHERE student_id = ? AND class_id = ?',
            (user_id, quiz['class_id'])
        )
        if not enrollment:
            return json_error('You are not enrolled in this class', status=403)

        # Check attempt count
        attempts_count = db.execute_one(
            'SELECT COUNT(*) as count FROM quiz_submissions WHERE quiz_id = ? AND student_id = ?',
            (quiz_id, user_id)
        )['count']

        if attempts_count >= 3:
            # Use the latest submission for display
            latest = db.execute_one(
                'SELECT score, total FROM quiz_submissions WHERE quiz_id = ? AND student_id = ? ORDER BY submitted_at DESC LIMIT 1',
                (quiz_id, user_id)
            )
            percentage = round((latest['score'] / latest['total']) * 100, 1) if latest['total'] > 0 else 0
            
            return json_success(
                message='Maximum attempts (3) reached',
                data={
                    'score': latest['score'],
                    'total': latest['total'],
                    'percentage': percentage,
                    'attempt_number': attempts_count,
                    'is_limit_reached': True
                },
                score=latest['score'],
                total=latest['total'],
                percentage=percentage,
                attempt_number=attempts_count,
                is_limit_reached=True
            )

        # Get correct answers and text for feedback
        questions = db.execute_query(
            'SELECT id, question_text, correct_option_index, options FROM quiz_questions WHERE quiz_id = ?',
            (quiz_id,)
        )

        if not questions:
            return json_error('Quiz has no questions', status=400)

        question_map = {}
        detailed_results = []
        
        for q in questions:
            qid = str(q['id'])
            try:
                opts = json.loads(q.get('options') or '[]')
            except Exception:
                opts = []
            
            question_map[qid] = {
                'text': q['question_text'],
                'correct': q['correct_option_index'],
                'options': opts,
                'option_count': len(opts)
            }

        expected_keys = set(question_map.keys())
        answer_keys = set(str(k) for k in answers.keys())

        if expected_keys != answer_keys:
            return json_error(f'Answers must include every question exactly once. Missing: {list(expected_keys - answer_keys)}, Extra: {list(answer_keys - expected_keys)}', status=400)

        normalized_answers = {}
        for qid, submitted in answers.items():
            sqid = str(qid)
            if sqid not in question_map:
                return json_error(f'Invalid question id: {sqid}', status=400)
            try:
                selected = int(submitted)
            except (TypeError, ValueError):
                return json_error(f'Invalid answer for question {sqid}', status=400)
            option_count = question_map[sqid]['option_count']
            if selected < 0 or (option_count and selected >= option_count):
                return json_error(f'Answer out of range for question {sqid}', status=400)
            normalized_answers[sqid] = selected

        # Calculate score and build details
        score = 0
        total = len(questions)
        logger.info(f"[SCORE_DEBUG] Quiz {quiz_id}, Questions: {len(questions)}, Answers: {len(normalized_answers)}")
        
        for qid, meta in question_map.items():
            user_idx = normalized_answers.get(qid)
            correct_idx = meta['correct']
            is_correct = str(user_idx) == str(correct_idx)
            
            if is_correct:
                score += 1
            
            # Get option texts
            user_text = meta['options'][user_idx] if meta['options'] and 0 <= user_idx < len(meta['options']) else "Unknown"
            correct_text = meta['options'][correct_idx] if meta['options'] and 0 <= correct_idx < len(meta['options']) else "Unknown"

            detailed_results.append({
                'question_id': qid,
                'question_text': meta['text'],
                'user_answer': user_text,
                'correct_answer': correct_text,
                'is_correct': is_correct,
                'user_option_index': user_idx,
                'correct_option_index': correct_idx
            })

        # ── ATTEMPT-GATED ANSWER VISIBILITY ──
        # attempt_number = attempts_count + 1 (computed below)
        current_attempt = attempts_count + 1
        show_answers = current_attempt >= 3

        # SECURITY: Strip correct answers from response for attempts 1-2
        if not show_answers:
            for dr in detailed_results:
                dr.pop('correct_answer', None)
                dr.pop('correct_option_index', None)
        
        logger.info(f"[SCORE_DEBUG] Final score: {score}/{total}")

        # Save submission
        try:
            submission_id = db.execute_insert(
                'INSERT INTO quiz_submissions (quiz_id, student_id, score, total, answers, duration_seconds) VALUES (?, ?, ?, ?, ?, ?)',
                (quiz_id, user_id, score, total, json.dumps(normalized_answers), duration)
            )
        except Exception as db_error:
            logger.exception('Failed to save quiz submission')
            return json_error('Failed to save submission', status=500, data={'details': str(db_error)})

        # Calculate percentage
        percentage = round((score / total) * 100, 1) if total > 0 else 0

        adaptive_insights = {
            'knowledge_gaps_detected': 0,
            'gaps': [],
            'recommendations_generated': 0,
            'recommendations': []
        }

        # Update adaptive engine immediately (best effort, never fail submission)
        mistake_notes_data = []
        try:
            class_id = quiz['class_id']
            adaptive.update_student_metrics(user_id, class_id)
            gaps = adaptive.analyze_knowledge_gaps(user_id, class_id) or []
            recs = adaptive.generate_recommendations(user_id, class_id) or []
            adaptive_insights = {
                'knowledge_gaps_detected': len(gaps),
                'gaps': gaps[:5],
                'recommendations_generated': len(recs),
                'recommendations': recs[:5]
            }
            
            # Update adaptive quiz profile
            try:
                adaptive_quiz.update_adaptive_profile(user_id, class_id, score, total)
            except Exception as e:
                logger.error(f"Adaptive profile update failed: {e}")

            # Update skill tree progress
            try:
                skill_tree.update_progress_after_quiz(user_id, quiz_id, class_id, score, total)
            except Exception as e:
                logger.error(f"Skill tree progress update failed: {e}")

            # Regenerate exam prediction
            try:
                exam_predictor.generate_prediction(user_id)
            except Exception as e:
                logger.error(f"Exam prediction update failed: {e}")

            # Recalculate class leaderboard
            try:
                leaderboard_engine.recalculate_class(class_id)
            except Exception as e:
                logger.error(f"Leaderboard recalculation failed: {e}")

            # Generate mistake notes for wrong answers
            wrong_questions = [r for r in detailed_results if not r['is_correct']]
            if wrong_questions:
                try:
                    mistake_notes_data = adaptive_quiz.generate_mistake_notes(
                        user_id, quiz_id, class_id, 
                        [{'question_id': wq.get('question_id', 0),
                          'question_text': wq['question_text'],
                          'user_answer': wq['user_answer'],
                          'correct_answer': wq['correct_answer'],
                          'topic_tag': ''} for wq in wrong_questions]
                    )
                except Exception as e:
                    logger.error(f"Mistake notes generation failed: {e}")

            # Check for badges
            awarded_badges = []
            try:
                # Quiz badges
                quiz_badges = badge_service.check_quiz_badges(user_id, quiz_id, score, total)
                if quiz_badges:
                    awarded_badges.extend(quiz_badges)
                
                # Course completion badge
                completion_badge = badge_service.check_module_completion(user_id, class_id)
                if completion_badge:
                    awarded_badges.append(completion_badge)
                    
            except Exception as e:
                logger.error(f"Badge check failed: {e}")

        except Exception as e:
            logger.error(f"Adaptive update failed for user={user_id} quiz={quiz_id}: {e}")
            awarded_badges = [] # Ensure defined via fallback if outer except catches

        # SECURITY: Strip mistake notes for attempts 1-2 (they contain correct answers)
        safe_mistake_notes = mistake_notes_data if show_answers else []

        return json_success(
            message='Quiz submitted successfully',
            data={
                'score': score,
                'total': total,
                'percentage': percentage,
                'attempt_number': current_attempt,
                'show_answers': show_answers,
                'adaptive_insights': adaptive_insights,
                'question_results': detailed_results,
                'badges': awarded_badges,
                'mistake_notes': safe_mistake_notes
            },
            score=score,
            total=total,
            percentage=percentage,
            attempt_number=current_attempt,
            show_answers=show_answers,
            adaptive_insights=adaptive_insights,
            question_results=detailed_results,
            badges=awarded_badges,
            mistake_notes=safe_mistake_notes
        )
    except Exception as e:
        logger.exception('Unhandled error in quiz submission')
        return json_error('Failed to submit quiz', status=500, data={'details': str(e)})


@app.route('/api/quiz/<int:quiz_id>/submit', methods=['POST'])
@api_login_required
@rate_limit(calls=8, period=60)
def submit_quiz_by_id(quiz_id):
    """New route to support RESTful submit endpoint: /api/quiz/<id>/submit"""
    data = get_json_payload()
    if data is None:
        return json_error('Invalid JSON payload', status=400)
    data['quiz_id'] = quiz_id
    return _handle_quiz_submission(data, get_current_user_id())


# ============================================================================
# SKILL TREE ROUTES
# ============================================================================

@app.route('/api/skill-tree/<int:class_id>')
@api_login_required
def get_skill_tree(class_id):
    """Get the skill tree for a class with student progress."""
    user_id = get_current_user_id()
    try:
        # Auto-generate tree if it doesn't exist
        existing = db.execute_query('SELECT id FROM skill_tree_nodes WHERE class_id = ?', (class_id,))
        if not existing:
            skill_tree.generate_skill_tree(class_id)

        nodes = skill_tree.get_skill_tree(class_id, user_id)
        return json_success(data={'nodes': nodes, 'class_id': class_id})
    except Exception as e:
        logger.error(f"Error fetching skill tree: {e}")
        return json_error('Failed to load skill tree', status=500)


@app.route('/api/skill-tree/generate', methods=['POST'])
@api_login_required
def generate_skill_tree_route():
    """Generate or regenerate skill tree for a class."""
    data = get_json_payload()
    if data is None:
        return json_error('Invalid JSON payload', status=400)
    class_id = data.get('class_id')
    if not class_id:
        return json_error('class_id required', status=400)
    try:
        nodes = skill_tree.generate_skill_tree(class_id)
        user_id = get_current_user_id()
        tree = skill_tree.get_skill_tree(class_id, user_id)
        return json_success(message='Skill tree generated', data={'nodes': tree})
    except Exception as e:
        logger.error(f"Error generating skill tree: {e}")
        return json_error('Failed to generate skill tree', status=500)


# ============================================================================
# ANALYTICS ROUTES
# ============================================================================

@app.route('/api/analytics')
@login_required
def get_analytics():
    """Get analytics data"""
    if session['role'] == 'student':
        # Student sees their own metrics
        metrics = db.execute_query(
            '''SELECT sm.*, c.title as class_name
               FROM student_metrics sm
               JOIN classes c ON sm.class_id = c.id
               WHERE sm.user_id = ?''',
            (get_current_user_id(),)
        )
        return jsonify(metrics)
    else:
        # Teacher sees all students in their classes
        class_id = request.args.get('class_id')
        
        if class_id:
            metrics = db.execute_query(
                '''SELECT sm.*, u.name as student_name
                   FROM student_metrics sm
                   JOIN users u ON sm.user_id = u.id
                   WHERE sm.class_id = ?
                   ORDER BY sm.rating DESC''',
                (class_id,)
            )
        else:
            metrics = db.execute_query(
                '''SELECT sm.*, u.name as student_name, c.title as class_name
                   FROM student_metrics sm
                   JOIN users u ON sm.user_id = u.id
                   JOIN classes c ON sm.class_id = c.id
                   WHERE c.teacher_id = ?
                   ORDER BY sm.rating DESC''',
                (get_current_user_id(),)
            )
        
        return jsonify(metrics)

@app.route('/api/class/<int:class_id>/progress')
@login_required
def get_class_progress(class_id):
    """Get student progress in a class"""
    metrics = db.execute_one(
        'SELECT * FROM student_metrics WHERE user_id = ? AND class_id = ?',
        (get_current_user_id(), class_id)
    )
    
    if not metrics:
        return jsonify({'message': 'No progress data yet'}), 200
    
    return jsonify(metrics)

# ============================================================================
# LEARNING PATH & STUDENT DASHBOARD API
# ============================================================================

@app.route('/api/learning-path/<int:class_id>')
@login_required
def get_learning_path(class_id):
    """Get the learning path for a specific class"""
    user_id = get_current_user_id()
    
    # 1. Verify enrollment
    enrollment = db.execute_one(
        'SELECT id FROM enrollments WHERE student_id = ? AND class_id = ?',
        (user_id, class_id)
    )
    if not enrollment:
        return jsonify({'error': 'Not enrolled in this class'}), 403

    # 2. Get modules with progress
    modules = learning_path_service.get_subject_modules(class_id, user_id)
    
    # 3. Get next recommended action
    next_action = learning_path_service.get_next_recommended_action(class_id, user_id)
    
    return jsonify({
        'success': True,
        'modules': modules,
        'next_action': next_action
    })

@app.route('/api/student/recommendations')
@login_required
def get_student_recommendations():
    """Get personalized recommendations across all enrolled classes"""
    user_id = get_current_user_id()
    
    # Get all enrollments
    enrollments = db.execute_query(
        'SELECT class_id FROM enrollments WHERE student_id = ?',
        (user_id,)
    )
    
    all_recs = []
    seen_ids = set()
    
    for enrollment in enrollments:
        class_id = enrollment['class_id']
        # Use existing service method
        recs = adaptive.generate_recommendations(user_id, class_id)
        
        # Deduplicate and add
        for rec in recs:
            # Create a unique key for deduplication
            key = f"{rec.get('type')}_{rec.get('content_id')}_{rec.get('title')}"
            if key not in seen_ids:
                seen_ids.add(key)
                all_recs.append(rec)
    
    # Sort by priority desc
    all_recs.sort(key=lambda x: x.get('priority', 0), reverse=True)
    
    return jsonify({'success': True, 'recommendations': all_recs[:10]})

@app.route('/api/student/knowledge-gaps')
@login_required
def get_student_knowledge_gaps():
    """Get knowledge gaps across all enrolled classes"""
    user_id = get_current_user_id()
    
    enrollments = db.execute_query(
        'SELECT class_id FROM enrollments WHERE student_id = ?',
        (user_id,)
    )
    
    all_gaps = []
    for enrollment in enrollments:
        class_id = enrollment['class_id']
        gaps = adaptive.analyze_knowledge_gaps(user_id, class_id)
        all_gaps.extend(gaps)
        
    # Limit to top 10
    return jsonify({'success': True, 'gaps': all_gaps[:10]})

@app.route('/api/student/analytics-overview')
@login_required
def get_student_analytics_overview():
    """Get aggregated analytics for the student dashboard"""
    user_id = get_current_user_id()
    
    # 1. Average Score (across all classes)
    metrics = db.execute_query(
        'SELECT quiz_score FROM student_metrics WHERE user_id = ?',
        (user_id,)
    )
    
    avg_score = 0
    if metrics:
        total = sum(m['quiz_score'] for m in metrics if m['quiz_score'] is not None)
        avg_score = total / len(metrics)
        
    # 2. Completed Modules
    completed_modules = db.execute_one(
        "SELECT COUNT(*) as count FROM student_module_progress WHERE user_id = ? AND status = 'COMPLETED'",
        (user_id,)
    )
    completed_count = completed_modules['count'] if completed_modules else 0
    
    # 3. Total Time (from quiz submissions)
    time_data = db.execute_one(
        "SELECT SUM(duration_seconds) as total_seconds FROM quiz_submissions WHERE student_id = ?",
        (user_id,)
    )
    total_seconds = time_data['total_seconds'] or 0
    total_minutes = int(total_seconds / 60)
    
    # 4. Learning Streak (Mock logic for now - check last login?)
    # For now, return 1 if there's recent activity, else 0
    streak = 1 # Placeholder

    # 5. Subject Progress (Timeline Data)
    subject_progress = []
    enrollments = db.execute_query('SELECT class_id FROM enrollments WHERE student_id = ?', (user_id,))
    
    for enrollment in enrollments:
        class_id = enrollment['class_id']
        class_info = db.execute_one('SELECT title, subject FROM classes WHERE id = ?', (class_id,))
        
        # Get modules status
        modules = learning_path_service.get_subject_modules(class_id, user_id)
        total_modules = len(modules)
        completed_mod = sum(1 for m in modules if m.get('status') == 'completed')
        
        percent = 0
        if total_modules > 0:
            percent = round((completed_mod / total_modules) * 100)
            
        subject_progress.append({
            'class_id': class_id,
            'title': class_info['title'] if class_info else 'Unknown Class',
            'subject': class_info['subject'] if class_info else 'General',
            'total_modules': total_modules,
            'completed_modules': completed_mod,
            'percent': percent
        })
    
    return jsonify({
        'success': True,
        'data': {
            'average_score': avg_score,
            'completed_modules': completed_count,
            'learning_streak': streak,
            'total_time_minutes': total_minutes,
            'subject_progress': subject_progress
        }
    })

@app.route('/api/classes/available')
@login_required
def get_available_classes():
    """Get classes available for enrollment (excluding already enrolled)"""
    user_id = get_current_user_id()
    
    # Get all classes except those the student is already enrolled in
    query = '''
        SELECT c.id, c.title, c.subject, c.code, u.name as teacher_name
        FROM classes c
        JOIN users u ON c.teacher_id = u.id
        WHERE c.id NOT IN (
            SELECT class_id FROM enrollments WHERE student_id = ?
        )
        ORDER BY c.created_at DESC
    '''
    
    classes = db.execute_query(query, (user_id,))
    return jsonify(classes)

# ============================================================================
# AI ROUTES (KyKnoX)
# ============================================================================

@app.route('/quiz/<int:quiz_id>')
@login_required
def quiz_view_page(quiz_id):
    """Quiz taking page"""
    # Verify quiz exists
    quiz = db.execute_one('SELECT id, title FROM quizzes WHERE id = ?', (quiz_id,))
    if not quiz:
        return "Quiz not found", 404
        
    # Check access (student must be enrolled)
    if session['role'] == 'student':
        quiz_data = db.execute_one('SELECT class_id FROM quizzes WHERE id = ?', (quiz_id,))
        enrollment = db.execute_one(
            'SELECT id FROM enrollments WHERE student_id = ? AND class_id = ?',
            (get_current_user_id(), quiz_data['class_id'])
        )
        if not enrollment:
            return "Access denied", 403
            
    return render_template('quiz_view.html', quiz_id=quiz_id)

@app.route('/api/chatbot', methods=['POST'])
@api_login_required
@rate_limit(calls=12, period=60)
def chatbot():
    """KyKnoX AI chatbot endpoint with multilingual support"""
    data = request.json or {}
    prompt = sanitize_input(data.get('prompt', ''), max_length=2000)
    mode = data.get('mode', 'expert')
    language = data.get('language', 'english')  # NEW: language parameter

    if not prompt:
        return jsonify({'success': False, 'error': 'Prompt required', 'message': 'Prompt required'}), 400

    # Get student context for personalization
    try:
        student_context = adaptive.get_student_context(get_current_user_id()) or {}
    except Exception:
        student_context = {}

    # Get role from session
    role = session.get('role', 'student')

    # Generate AI response with language support
    try:
        # Pass language to AI generation
        answer, provider = kyknox.generate_response(prompt, mode, student_context, role, language=language)
        rendered_answer = kyknox.render_markdown(answer)
    except Exception as e:
        logger.exception('AI generation failed')
        return jsonify({'success': False, 'error': 'AI generation failed', 'message': str(e)}), 500

    # Save to database (best-effort)
    try:
        db.execute_insert(
            'INSERT INTO ai_queries (user_id, prompt, response, provider, mode) VALUES (?, ?, ?, ?, ?)',
            (get_current_user_id(), prompt, answer, provider, mode)
        )
    except Exception:
        logger.exception('Failed to save ai query')

    return jsonify({
        'success': True,
        'reply': rendered_answer,
        'raw': answer,
        'provider': provider,
        'personalized': bool(student_context.get('weak_topics'))
    }), 200

@app.route('/api/ai/history')
@api_login_required
def get_ai_history():
    """Get recent AI chat history"""
    history = db.execute_query(
        'SELECT prompt, response, created_at FROM ai_queries WHERE user_id = ? ORDER BY created_at DESC LIMIT 50',
        (get_current_user_id(),)
    )
    # Render markdown for history items too
    for item in history:
        item['response'] = kyknox.render_markdown(item['response'])
        
    return jsonify(history)

@app.route('/api/student/recommendations')
@api_login_required
def get_recommendations():
    """Get AI recommendations for student"""
    user_id = get_current_user_id()
    rec_cols = {row.get('name') for row in db.execute_query('PRAGMA table_info(recommendations)')}

    # Try getting from DB first
    if {'content_type', 'content_id', 'reason'}.issubset(rec_cols):
        recs = db.execute_query(
            '''SELECT id, content_type as type, content_id, reason, priority, created_at
               FROM recommendations 
               WHERE user_id = ? AND is_completed = 0 
               ORDER BY priority DESC, created_at DESC LIMIT 8''',
            (user_id,)
        )
    else:
        recs = db.execute_query(
            '''SELECT id, type, title, description, resource_url, priority, created_at
               FROM recommendations 
               WHERE user_id = ? AND is_completed = 0 
               ORDER BY priority DESC, created_at DESC LIMIT 8''',
            (user_id,)
        )
    
    # If no recommendations, generate some basic ones using Adaptive Learning
    if not recs:
        # Check for enrolled classes to generate context
        enrolled = db.execute_query(
            'SELECT class_id FROM enrollments WHERE student_id = ? LIMIT 1',
             (user_id,)
        )
        if enrolled:
             # Trigger generation (this would normally be async)
             adaptive.generate_recommendations(user_id, enrolled[0]['class_id'])
             # Fetch again
             if {'content_type', 'content_id', 'reason'}.issubset(rec_cols):
                 recs = db.execute_query(
                    '''SELECT id, content_type as type, content_id, reason, priority, created_at
                       FROM recommendations 
                       WHERE user_id = ? AND is_completed = 0 
                       ORDER BY priority DESC, created_at DESC LIMIT 8''',
                    (user_id,)
                )
             else:
                 recs = db.execute_query(
                    '''SELECT id, type, title, description, resource_url, priority, created_at
                       FROM recommendations 
                       WHERE user_id = ? AND is_completed = 0 
                       ORDER BY priority DESC, created_at DESC LIMIT 8''',
                    (user_id,)
                )

    # Normalize recommendation cards
    normalized = []
    for rec in recs:
        normalized.append({
            'id': rec.get('id'),
            'type': rec.get('type') or rec.get('content_type') or 'resource',
            'title': rec.get('title') or f"Recommended {rec.get('type', 'content').title()}",
            'description': rec.get('description') or rec.get('reason') or 'Based on your recent performance',
            'resource_url': rec.get('resource_url'),
            'priority': rec.get('priority', 1)
        })

    return json_success(message='Recommendations loaded', data={'recommendations': normalized}, recommendations=normalized)



@app.route('/student/micro-learning')
@login_required
@student_required
def student_micro_learning():
    """Micro-Learning Dashboard"""
    user_id = get_current_user_id()
    
    # Get enrolled classes (use first one for now or let user select)
    # Ideally passed via query param or session
    class_id = request.args.get('class_id')
    
    if not class_id:
        # Default to first enrolled class
        enrollment = db.execute_one('SELECT class_id FROM enrollments WHERE student_id = ? LIMIT 1', (user_id,))
        if enrollment:
            class_id = enrollment['class_id']
        else:
            return render_template('student_dashboard.html', error="Please join a class first.")

    # Get class title for AI context
    class_info = db.execute_one('SELECT title FROM classes WHERE id = ?', (class_id,))
    class_title = class_info['title'] if class_info else 'General'

    # Get Daily Tasks
    daily_data = micro_learning.get_daily_tasks(user_id, class_id, class_title)
    
    return render_template('micro_learning.html', data=daily_data, class_id=class_id)

@app.route('/api/micro-learning/complete', methods=['POST'])
@login_required
def complete_micro_task():
    """Mark a micro-task item as complete"""
    data = request.json
    item_type = data.get('type')
    item_id = data.get('id')
    task_id = data.get('task_id')
    
    if not all([item_type, item_id, task_id]):
        return json_error("Missing data")
        
    success = micro_learning.mark_completed(item_type, item_id, task_id)
    if success:
        # Fetch updated stats
        updated_task = micro_learning._fetch_full_task_details(task_id)
        return json_success("Marked complete", data=updated_task['stats'])
    else:
        return json_error("Failed to update status")

@app.route('/api/micro-learning/refresh', methods=['POST'])
@login_required
@student_required
def refresh_micro_tasks():
    """Delete today's micro-learning tasks and regenerate fresh content"""
    user_id = get_current_user_id()
    data = request.json or {}
    class_id = data.get('class_id')

    if not class_id:
        enrollment = db.execute_one('SELECT class_id FROM enrollments WHERE student_id = ? LIMIT 1', (user_id,))
        if enrollment:
            class_id = enrollment['class_id']
        else:
            return json_error("No enrolled class found")

    class_info = db.execute_one('SELECT title FROM classes WHERE id = ?', (class_id,))
    class_title = class_info['title'] if class_info else 'General'

    try:
        new_data = micro_learning.refresh_tasks(user_id, class_id, class_title)
        return json_success("Tasks refreshed with new content", data=new_data)
    except Exception as e:
        logger.exception('Failed to refresh micro-learning tasks')
        return json_error("Failed to refresh tasks")

@app.route('/api/student/quiz-history')
@api_login_required
def get_student_quiz_history_api():
    """Get student's quiz submission history"""
    user_id = get_current_user_id()
    class_id = request.args.get('class_id', type=int)
    sort = request.args.get('sort', 'date')
    page = max(request.args.get('page', default=1, type=int), 1)
    per_page = min(max(request.args.get('per_page', default=10, type=int), 1), 50)

    order_by = 'qs.submitted_at DESC'
    if sort == 'score':
        order_by = '(qs.score * 100.0 / NULLIF(qs.total, 0)) DESC, qs.submitted_at DESC'
    elif sort == 'time':
        order_by = 'COALESCE(qs.duration_seconds, 0) ASC, qs.submitted_at DESC'

    params = [user_id]
    where_clause = 'WHERE qs.student_id = ?'
    if class_id:
        where_clause += ' AND c.id = ?'
        params.append(class_id)

    count_query = f'''
        SELECT COUNT(*) as total_count
        FROM quiz_submissions qs
        JOIN quizzes q ON qs.quiz_id = q.id
        JOIN classes c ON q.class_id = c.id
        {where_clause}
    '''
    total_count = db.execute_one(count_query, tuple(params))['total_count']
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    offset = (page - 1) * per_page

    history_query = f'''
        SELECT 
            qs.id,
            qs.quiz_id,
            q.title as quiz_title,
            c.id as class_id,
            c.title as class_name,
            qs.score as correct_answers,
            qs.total as total_questions,
            (qs.total - qs.score) as wrong_answers,
            ROUND(qs.score * 100.0 / NULLIF(qs.total, 0), 1) as score_percent,
            qs.duration_seconds,
            ROUND(COALESCE(qs.duration_seconds, 0) / 60.0, 1) as time_taken_minutes,
            qs.submitted_at,
            CASE
                WHEN (qs.score * 100.0 / NULLIF(qs.total, 0)) >= 80 THEN 'Easy'
                WHEN (qs.score * 100.0 / NULLIF(qs.total, 0)) >= 60 THEN 'Medium'
                ELSE 'Hard'
            END as difficulty,
            (SELECT COUNT(*) FROM quiz_submissions WHERE quiz_id = qs.quiz_id AND student_id = ? AND id <= qs.id) as attempt_number
           FROM quiz_submissions qs
           JOIN quizzes q ON qs.quiz_id = q.id
           JOIN classes c ON q.class_id = c.id
           {where_clause}
           ORDER BY {order_by}
           LIMIT ? OFFSET ?
    '''
    query_params = [user_id] + params + [per_page, offset]
    history = db.execute_query(history_query, tuple(query_params))

    return json_success(
        message='Quiz history loaded',
        data={
            'attempts': history,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'total_count': total_count
        },
        attempts=history,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_count=total_count
    )







@app.route('/api/live/create', methods=['POST'])
@login_required
@teacher_required
def create_live_session():
    """Create a new live class session"""
    data = request.json
    class_id = data.get('class_id')
    
    if not class_id:
        return jsonify({'error': 'Class ID required'}), 400
        
    # Check if session already active
    active = db.execute_one(
        'SELECT * FROM live_sessions WHERE class_id = ? AND is_active = 1',
        (class_id,)
    )
    
    if active:
        return jsonify({
            'room_name': active['room_name'],
            'message': 'Session already active'
        })
        
    # Generate unique room name: ClassName-TeacherName-Random
    import random
    import string
    
    class_info = db.execute_one('SELECT title FROM classes WHERE id = ?', (class_id,))
    if not class_info:
        return jsonify({'error': 'Class not found'}), 404
        
    clean_title = "".join(c for c in class_info['title'] if c.isalnum())
    clean_name = "".join(c for c in session.get('name', 'Teacher') if c.isalnum())
    random_suffix = "".join(random.choices(string.ascii_letters + string.digits, k=6))
    
    room_name = f"LearnVaultX-{clean_title}-{clean_name}-{random_suffix}"
    
    try:
        db.execute_insert(
            '''INSERT INTO live_sessions (class_id, room_name, started_by)
               VALUES (?, ?, ?)''',
            (class_id, room_name, get_current_user_id())
        )
        return jsonify({'room_name': room_name, 'message': 'Session created'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/live/end', methods=['POST'])
@login_required
@teacher_required
def end_live_session():
    """End an active live session"""
    data = request.json
    room_name = data.get('room_name')
    
    if not room_name:
        return jsonify({'error': 'Room name required'}), 400
        
    try:
        db.execute_update(
            '''UPDATE live_sessions 
               SET is_active = 0, ended_at = CURRENT_TIMESTAMP 
               WHERE room_name = ? AND started_by = ?''',
            (room_name, get_current_user_id())
        )
        return jsonify({'message': 'Session ended'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/live/<room_name>')
@login_required
def live_class_view(room_name):
    """Render the live class page with Jitsi Meet - OPTIMIZED"""
    
    # Single optimized query with all needed data
    session_info = db.execute_one(
        '''SELECT ls.room_name, ls.class_id, c.title as class_title, 
                  u.name as teacher_name, ls.started_by
           FROM live_sessions ls
           JOIN classes c ON ls.class_id = c.id
           JOIN users u ON ls.started_by = u.id
           WHERE ls.room_name = ? AND ls.is_active = 1
           LIMIT 1''',
        (room_name,)
    )
    
    # Fast fail if session not found
    if not session_info:
        flash('This live session has ended or does not exist.', 'info')
        return redirect(url_for('student_dashboard'))
    
    # Prepare user data for Jitsi (from session, no DB query needed)
    user_data = {
        'displayName': session.get('name', 'User'),
        'email': session.get('email', ''),
        'name': session.get('name', 'User')
    }
    
    # Render template immediately
    return render_template('live_class.html', 
                          room_name=room_name, 
                          class_title=session_info['class_title'],
                          instructor_name=session_info['teacher_name'],
                          is_teacher=(session.get('role') == 'teacher'),
                          user_data=user_data)

# ============================================================================
# LIVE CLASS ENDPOINTS (JITSI MEET INTEGRATION)
# ============================================================================

@app.route('/api/class/<int:class_id>/live/create', methods=['POST'])
@login_required
def create_live_class(class_id):
    """Create a live class session (teacher only)"""
    # Verify user is the teacher of this class
    class_info = db.execute_one(
        'SELECT * FROM classes WHERE id = ? AND teacher_id = ?',
        (class_id, get_current_user_id())
    )
    
    if not class_info:
        return jsonify({'error': 'Not authorized or class not found'}), 403
    
    data = request.json
    room_name = data.get('room_name', f"LearnVaultX-Class-{class_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    
    # Check if there's already an active session
    existing = db.execute_one(
        'SELECT * FROM live_sessions WHERE class_id = ? AND is_active = 1',
        (class_id,)
    )
    
    if existing:
        return jsonify({
            'message': 'Live session already active',
            'room_name': existing['room_name'],
            'session_id': existing['id']
        }), 200
    
    # Create new live session
    session_id = db.execute_insert(
        'INSERT INTO live_sessions (class_id, room_name, started_by, is_active) VALUES (?, ?, ?, 1)',
        (class_id, room_name, get_current_user_id())
    )
    
    logger.info(f"Live class created: {room_name} for class {class_id}")
    
    return jsonify({
        'message': 'Live session created',
        'room_name': room_name,
        'session_id': session_id,
        'jitsi_url': f"https://meet.jit.si/{room_name}"
    }), 201

@app.route('/api/class/<int:class_id>/live/join', methods=['GET'])
@login_required
def join_live_class(class_id):
    """Join an active live class session (students and teacher)"""
    # Check if user is enrolled or is the teacher
    enrollment = db.execute_one(
        '''SELECT e.*, c.teacher_id FROM enrollments e
           JOIN classes c ON e.class_id = c.id
           WHERE e.class_id = ? AND (e.student_id = ? OR c.teacher_id = ?)''',
        (class_id, get_current_user_id(), get_current_user_id())
    )
    
    if not enrollment:
        return jsonify({'error': 'Not enrolled in this class'}), 403
    
    # Get active session
    active_session = db.execute_one(
        'SELECT * FROM live_sessions WHERE class_id = ? AND is_active = 1',
        (class_id,)
    )
    
    if not active_session:
        return jsonify({'error': 'No active live session'}), 404
    
    return jsonify({
        'room_name': active_session['room_name'],
        'session_id': active_session['id'],
        'jitsi_url': f"https://meet.jit.si/{active_session['room_name']}"
    }), 200

@app.route('/api/class/<int:class_id>/live/status', methods=['GET'])
@login_required
def live_class_status(class_id):
    """Check if there's an active live session"""
    active_session = db.execute_one(
        'SELECT * FROM live_sessions WHERE class_id = ? AND is_active = 1',
        (class_id,)
    )
    
    if active_session:
        return jsonify({
            'active': True,
            'room_name': active_session['room_name'],
            'started_at': active_session['started_at']  # Fixed: was 'created_at', now correctly uses 'started_at'
        }), 200
    
    return jsonify({'active': False}), 200

@app.route('/api/class/<int:class_id>/live/end', methods=['POST'])
@login_required
def end_live_class(class_id):
    """End a live class session (teacher only)"""
    # Verify user is the teacher
    class_info = db.execute_one(
        'SELECT * FROM classes WHERE id = ? AND teacher_id = ?',
        (class_id, get_current_user_id())
    )
    
    if not class_info:
        return jsonify({'error': 'Not authorized'}), 403
    
    # End active session
    db.execute_update(
        'UPDATE live_sessions SET is_active = 0, ended_at = CURRENT_TIMESTAMP WHERE class_id = ? AND is_active = 1',
        (class_id,)
    )
    
    return jsonify({'message': 'Live session ended'}), 200


# ============================================================================
# SOCKET.IO EVENTS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected")
    emit('connection_status', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected")

@socketio.on('join_class')
def handle_join_class(data):
    """Join a class room"""
    class_id = data.get('class_id')
    if class_id:
        join_room(f"class_{class_id}")
        emit('joined_class', {'class_id': class_id}, room=f"class_{class_id}")

@socketio.on('leave_class')
def handle_leave_class(data):
    """Leave a class room"""
    class_id = data.get('class_id')
    if class_id:
        leave_room(f"class_{class_id}")

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================================
# INITIALIZATION
# ============================================================================

def initialize_database():
    """Initialize database schema"""
    try:
        db.init_schema('schema_new.sql')

        # Compatibility migrations for older/newer schema variants
        with db.get_db() as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS teacher_interventions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    teacher_id INTEGER NOT NULL,
                    class_id INTEGER NOT NULL,
                    alert_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    is_resolved INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES users(id),
                    FOREIGN KEY (teacher_id) REFERENCES users(id),
                    FOREIGN KEY (class_id) REFERENCES classes(id)
                );

                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_id INTEGER NOT NULL,
                    topic_name TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (class_id) REFERENCES classes(id)
                );

                CREATE TABLE IF NOT EXISTS question_topics (
                    question_id INTEGER NOT NULL,
                    topic_id INTEGER NOT NULL,
                    PRIMARY KEY (question_id, topic_id),
                    FOREIGN KEY (question_id) REFERENCES quiz_questions(id),
                    FOREIGN KEY (topic_id) REFERENCES topics(id)
                );

                CREATE TABLE IF NOT EXISTS knowledge_gaps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    topic_id INTEGER NOT NULL,
                    mastery_level REAL DEFAULT 0.0,
                    questions_attempted INTEGER DEFAULT 0,
                    questions_correct INTEGER DEFAULT 0,
                    last_assessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, topic_id),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (topic_id) REFERENCES topics(id)
                );
            ''')
            conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

# ============================================================================



# ============================================================================
# ANALYTICS PAGE ROUTES
# ============================================================================

@app.route('/student/analytics')
@login_required
def student_analytics_page():
    """Render student analytics dashboard"""
    return render_template('student_analytics.html')


@app.route('/student/quiz-history')
@login_required
def quiz_history_page():
    """Render quiz history page"""
    return render_template('quiz_history.html')


@app.route('/teacher/analytics')
@login_required
def teacher_analytics_page():
    """Render teacher analytics dashboard"""
    return render_template('teacher_analytics.html')


# ============================================================================
# SEO ROUTES
# ============================================================================

@app.route('/sitemap.xml')
def sitemap():
    """Generate sitemap.xml for search engines"""
    from flask import Response
    host = request.host_url.rstrip('/')
    pages = [
        {'loc': f'{host}/', 'priority': '1.0', 'changefreq': 'weekly'},
        {'loc': f'{host}/login', 'priority': '0.8', 'changefreq': 'monthly'},
        {'loc': f'{host}/register', 'priority': '0.8', 'changefreq': 'monthly'},
    ]
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for page in pages:
        xml += '  <url>\n'
        xml += f'    <loc>{page["loc"]}</loc>\n'
        xml += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
        xml += f'    <priority>{page["priority"]}</priority>\n'
        xml += '  </url>\n'
    xml += '</urlset>'
    return Response(xml, mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    """Serve robots.txt for search engines"""
    from flask import Response
    host = request.host_url.rstrip('/')
    content = f"""User-agent: *
Allow: /
Disallow: /student/
Disallow: /teacher/
Disallow: /api/
Disallow: /quiz/
Disallow: /live/
Disallow: /verify-login-otp
Disallow: /verify-signup-otp

Sitemap: {host}/sitemap.xml
"""
    return Response(content.strip(), mimetype='text/plain')


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('404.html'), 404

@app.errorhandler(403)
def forbidden(e):
    """Handle 403 errors"""
    return render_template('403.html'), 403

@app.errorhandler(500)
def internal_server_error(e):
    """Handle 500 errors"""
    logger.exception('Internal server error occurred')
    return render_template('500.html'), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Initialize database
    initialize_database()
    
    # Run server
    port = int(os.getenv('PORT', 5050))
    logger.info(f"Starting LearnVaultX server on port {port}")
    
    # Print localhost URL clearly
    print("\n" + "="*60)
    print(f"?? LearnVaultX is running!")
    print(f"?? Open in browser: http://127.0.0.1:{port}")
    print("="*60 + "\n")
    
    try:
        socketio.run(
            app,
            host='0.0.0.0',
            port=port,
            debug=False,
            use_reloader=False,
            log_output=True,
            allow_unsafe_werkzeug=True
        )
    except OSError as e:
        if "10048" in str(e) or "address already in use" in str(e).lower():
            # Port is busy, try fallback port
            fallback_port = port + 1
            print(f"\n??  Port {port} is busy, trying port {fallback_port}...\n")
            logger.warning(f"Port {port} in use, falling back to {fallback_port}")
            print("\n" + "="*60)
            print(f"?? LearnVaultX is running on FALLBACK PORT!")
            print(f"?? Open in browser: http://127.0.0.1:{fallback_port}")
            print(f"?? Or use: http://localhost:{fallback_port}")
            print("="*60 + "\n")
            socketio.run(
                app,
                host='0.0.0.0',
                port=fallback_port,
                debug=True,
                use_reloader=False,
                log_output=True,
                allow_unsafe_werkzeug=True
            )
        else:
            raise

