"""
Authentication Blueprint for LearnVaultX
Handles login, registration, OTP verification, and password resets.
"""
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from datetime import datetime
import os

auth_bp = Blueprint('auth', __name__)

from app import (
    db, email_service, logger, rate_limit, get_json_payload, 
    json_error, json_success, validate_email, validate_password, 
    sanitize_input, hash_password, verify_password
)


@auth_bp.route('/')
def index():
    if 'user_id' in session:
        if session['role'] == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        return redirect(url_for('student_dashboard'))
    return render_template('home.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next', '')
    if request.method == 'POST':
        # Handled by API
        return render_template('login.html', next=next_url)
    return render_template('login.html', next=next_url)

@auth_bp.route('/api/login', methods=['POST'])
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

@auth_bp.route('/register', methods=['GET'])
def register():
    return render_template('register.html')

@auth_bp.route('/api/register', methods=['POST'])
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

@auth_bp.route('/verify-signup-otp')
def verify_signup_otp_page():
    """Render signup OTP verification page."""
    if 'signup_otp_email' not in session:
        return redirect(url_for('auth.register'))
    return render_template('verify_signup_otp.html')

@auth_bp.route('/api/verify-signup-otp', methods=['POST'])
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

@auth_bp.route('/api/resend-signup-otp', methods=['POST'])
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

@auth_bp.route('/verify-login-otp')
def verify_login_otp_page():
    """Render login OTP verification page."""
    if 'login_otp_email' not in session:
        return redirect(url_for('auth.login'))
    return render_template('verify_login_otp.html')

@auth_bp.route('/api/verify-login-otp', methods=['POST'])
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

@auth_bp.route('/api/resend-login-otp', methods=['POST'])
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

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/api/health')
def health_check():
    """Health check endpoint to verify backend is running"""
    return jsonify({
        'status': 'ok',
        'message': 'LearnVaultX backend is running',
        'database': 'PostgreSQL',
        'timestamp': datetime.now().isoformat()
    }), 200



@auth_bp.route('/api/speed-test')
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

@auth_bp.route('/test-connection')
def test_connection():
    """Test page to verify backend connection"""
    return render_template('test_connection.html')

# ============================================================================
# FORGOT PASSWORD — OTP FLOW
# ============================================================================

@auth_bp.route('/forgot-password')
def forgot_password_page():
    """Render the forgot-password email entry page."""
    return render_template('forgot_password.html')

@auth_bp.route('/verify-otp')
def verify_otp_page():
    """Render OTP verification page. Requires email in session."""
    if 'reset_email' not in session:
        return redirect(url_for('auth.forgot_password_page'))
    return render_template('verify_otp.html')

@auth_bp.route('/reset-password')
def reset_password_page():
    """Render password reset page. Requires verified OTP."""
    if not session.get('otp_verified'):
        return redirect(url_for('auth.forgot_password_page'))
    return render_template('reset_password.html')


@auth_bp.route('/api/forgot-password/send-otp', methods=['POST'])
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


@auth_bp.route('/api/forgot-password/verify-otp', methods=['POST'])
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


@auth_bp.route('/api/forgot-password/resend-otp', methods=['POST'])
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


@auth_bp.route('/api/forgot-password/reset-password', methods=['POST'])
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
