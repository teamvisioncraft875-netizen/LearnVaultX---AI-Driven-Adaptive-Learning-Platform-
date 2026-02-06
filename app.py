from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import json
import time
import logging
from dotenv import load_dotenv
from modules import db_manager, adaptive_learning_new, email_service, kyknox_ai_new, demo_data_generator

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure Uploads
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize Services
db = db_manager.DatabaseManager('learnvault.db')
adaptive = adaptive_learning_new.AdaptiveEngine(db)
kyknox = kyknox_ai_new.KyKnoX()
data_generator = demo_data_generator.DemoDataGenerator(db)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper Functions
def get_current_user_id():
    return session.get('user_id')

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
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
    if not data.get('questions') or len(data['questions']) == 0:
        return False, "At least one question required"
    return True, ""

def hash_password(password):
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_hash, password):
    return stored_hash == hash_password(password)

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
    if request.method == 'POST':
        # Handled by API
        return render_template('login.html')
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
        
    user = db.execute_one('SELECT * FROM users WHERE email = ?', (email,))
    
    if user and verify_password(user['password_hash'], password):
        session['user_id'] = user['id']
        session['name'] = user['name']
        session['role'] = user['role']
        
        # Determine redirect URL
        redirect_url = '/teacher/dashboard' if user['role'] == 'teacher' else '/student/dashboard'
        
        return jsonify({
            'message': 'Login successful',
            'redirect': redirect_url,
            'user': {'id': user['id'], 'name': user['name'], 'role': user['role']}
        }), 200
        
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/register', methods=['GET'])
def register():
    return render_template('register.html')

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    name = sanitize_input(data.get('name'))
    email = data.get('email', '').strip().lower()
    password = data.get('password')
    role = data.get('role', 'student')
    
    if not name or not email or not password:
        return jsonify({'error': 'All fields required'}), 400
        
    if not validate_email(email):
        return jsonify({'error': 'Invalid email format'}), 400
        
    is_valid, error_msg = validate_password(password)
    if not is_valid:
        return jsonify({'error': error_msg}), 400
        
    # Check if user exists
    existing = db.execute_one('SELECT id FROM users WHERE email = ?', (email,))
    if existing:
        return jsonify({'error': 'Email already registered'}), 400
        
    # Create user
    password_hash = hash_password(password)
    user_id = db.execute_insert(
        'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
        (name, email, password_hash, role)
    )
    
    # Auto login
    session['user_id'] = user_id
    session['name'] = name
    session['role'] = role
    
    redirect_url = '/teacher/dashboard' if role == 'teacher' else '/student/dashboard'
    
    return jsonify({
        'message': 'Registration successful',
        'redirect': redirect_url
    }), 201

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/forgot-password/send-otp', methods=['POST'])
def send_password_reset_otp():
    """Send OTP for password reset"""
    data = request.json
    email = data.get('email', '').lower().strip()
    
    if not email or not validate_email(email):
        return jsonify({'error': 'Valid email required'}), 400
    
    # Check if user exists
    user = db.execute_one('SELECT id FROM users WHERE email = ?', (email,))
    if not user:
        # Don't reveal if email exists for security
        return jsonify({'message': 'If email exists, OTP has been sent'}), 200
    
    # Generate OTP
    otp = email_service.generate_otp()
    expires_at = email_service.get_otp_expiry()
    
    # Save OTP to database
    db.execute_insert(
        'INSERT INTO password_reset_otp (email, otp, expires_at) VALUES (?, ?, ?)',
        (email, otp, expires_at)
    )
    
    # Send email
    if email_service.send_otp_email(email, otp):
        logger.info(f"Password reset OTP sent to {email}")
        return jsonify({'message': 'OTP sent to email'}), 200
    else:
        return jsonify({'error': 'Failed to send email'}), 500

@app.route('/api/forgot-password/verify-otp', methods=['POST'])
def verify_password_reset_otp():
    """Verify OTP and reset password"""
    data = request.json
    email = data.get('email', '').lower().strip()
    otp = data.get('otp', '')
    new_password = data.get('new_password', '')
    
    if not email or not otp or not new_password:
        return jsonify({'error': 'All fields required'}), 400
    
    is_valid, error_msg = validate_password(new_password)
    if not is_valid:
        return jsonify({'error': error_msg}), 400
    
    # Verify OTP
    otp_record = db.execute_one(
        'SELECT * FROM password_reset_otp WHERE email = ? AND otp = ? AND used = 0 AND expires_at > ?',
        (email, otp, datetime.now())
    )
    
    if not otp_record:
        return jsonify({'error': 'Invalid or expired OTP'}), 400
    
    # Update password
    password_hash = hash_password(new_password)
    db.execute_update('UPDATE users SET password_hash = ? WHERE email = ?', (password_hash, email))
    
    # Mark OTP as used
    db.execute_update('UPDATE password_reset_otp SET used = 1 WHERE id = ?', (otp_record['id'],))
    
    logger.info(f"Password reset successful for {email}")
    return jsonify({'message': 'Password reset successful'}), 200

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
@login_required
@teacher_required
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
@login_required
@teacher_required
def create_class():
    """Create a new class"""
    data = request.json
    title = sanitize_input(data.get('title', ''))
    description = sanitize_input(data.get('description', ''), max_length=2000)
    
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    
    class_id = db.execute_insert(
        'INSERT INTO classes (title, description, teacher_id) VALUES (?, ?, ?)',
        (title, description, get_current_user_id())
    )
    
    logger.info(f"Class created: {title} (ID: {class_id})")
    return jsonify({'message': 'Class created', 'class_id': class_id}), 201

@app.route('/api/student/classes')
@login_required
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

@app.route('/api/classes/available')
@login_required
def get_available_classes():
    """Get classes available for enrollment"""
    classes = db.execute_query(
        '''SELECT c.*, u.name as teacher_name
           FROM classes c
           JOIN users u ON c.teacher_id = u.id
           WHERE c.id NOT IN (
               SELECT class_id FROM enrollments WHERE student_id = ?
           )
           ORDER BY c.created_at DESC''',
        (get_current_user_id(),)
    )
    return jsonify(classes)

@app.route('/api/user/data')
@login_required
def get_user_data():
    """Get user data with enrolled classes for student dashboard"""
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
        return jsonify({'classes': classes})
    return jsonify({'classes': []})

@app.route('/api/browse_classes')
@login_required
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
@login_required
@teacher_required
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

@app.route('/api/join_class', methods=['POST'])
@login_required
def join_class():
    """Enroll student in a class"""
    data = request.json
    class_id = data.get('class_id')
    
    if not class_id:
        return jsonify({'error': 'Class ID required'}), 400
    
    # Check if already enrolled
    existing = db.execute_one(
        'SELECT id FROM enrollments WHERE student_id = ? AND class_id = ?',
        (get_current_user_id(), class_id)
    )
    
    if existing:
        return jsonify({'error': 'Already enrolled'}), 400
    
    db.execute_insert(
        'INSERT INTO enrollments (student_id, class_id) VALUES (?, ?)',
        (get_current_user_id(), class_id)
    )
    
    logger.info(f"Student {get_current_user_id()} enrolled in class {class_id}")
    return jsonify({'message': 'Enrolled successfully'}), 201

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
    """Upload lecture file"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    class_id = request.form.get('class_id')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Validate file type
    allowed_extensions = {'pdf', 'ppt', 'pptx', 'doc', 'docx', 'txt', 'mp4', 'mp3'}
    if not validate_file_type(file.filename, allowed_extensions):
        return jsonify({'error': 'Invalid file type'}), 400
    
    if file and class_id:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        file_size = os.path.getsize(filepath)
        
        lecture_id = db.execute_insert(
            'INSERT INTO lectures (class_id, filename, filepath, file_size) VALUES (?, ?, ?, ?)',
            (class_id, filename, filepath, file_size)
        )
        
        logger.info(f"Lecture uploaded: {filename} (ID: {lecture_id}, Class: {class_id})")
        return jsonify({'message': 'Lecture uploaded', 'filename': filename, 'id': lecture_id}), 201
    
    return jsonify({'error': 'Invalid request'}), 400

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
    data = request.json
    
    # Validate quiz data
    is_valid, error_msg = validate_quiz_data(data)
    if not is_valid:
        return jsonify({'error': error_msg}), 400
    
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
    return jsonify({'message': 'Quiz created', 'quiz_id': quiz_id}), 201

@app.route('/api/class/<int:class_id>/quizzes')
@login_required
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

@app.route('/api/quiz/<int:quiz_id>')
@login_required
def get_quiz(quiz_id):
    """Get quiz details with questions"""
    quiz = db.execute_one('SELECT * FROM quizzes WHERE id = ?', (quiz_id,))
    if not quiz:
        return jsonify({'error': 'Quiz not found'}), 404
    
    questions = db.execute_query(
        'SELECT id, question_text, options, explanation FROM quiz_questions WHERE quiz_id = ?',
        (quiz_id,)
    )
    
    quiz_data = dict(quiz)
    quiz_data['questions'] = questions
    for q in quiz_data['questions']:
        q['options'] = json.loads(q['options'])
    
    return jsonify(quiz_data)

@app.route('/api/submit_quiz', methods=['POST'])
@login_required
def submit_quiz():
    """Submit quiz answers with optional adaptive learning"""
    try:
        print("[SUBMIT_QUIZ] ===== STARTING QUIZ SUBMISSION =====")
        
        data = request.json
        quiz_id = data.get('quiz_id')
        answers = data.get('answers', {})
        duration = data.get('duration', 0)
        
        print(f"[SUBMIT_QUIZ] Received: quiz_id={quiz_id}, answers={len(answers)}, duration={duration}s")
        
        if not quiz_id:
            print("[SUBMIT_QUIZ] ERROR: Missing quiz_id")
            return jsonify({'success': False, 'error': 'Quiz ID required'}), 400
        
        # Check for duplicate submission
        existing = db.execute_one(
            'SELECT id, score, total FROM quiz_submissions WHERE quiz_id = ? AND student_id = ?',
            (quiz_id, get_current_user_id())
        )
        
        if existing:
            print(f"[SUBMIT_QUIZ] Duplicate submission - returning existing result")
            percentage = round((existing['score'] / existing['total']) * 100, 1) if existing['total'] > 0 else 0
            return jsonify({
                'success': True,
                'message': 'Quiz already submitted',
                'score': existing['score'],
                'total': existing['total'],
                'percentage': percentage,
                'adaptive_insights': {
                    'knowledge_gaps_detected': 0,
                    'gaps': [],
                    'recommendations_generated': 0,
                    'recommendations': []
                }
            }), 200
        
        # Get correct answers
        questions = db.execute_query(
            'SELECT id, correct_option_index FROM quiz_questions WHERE quiz_id = ?',
            (quiz_id,)
        )
        
        if not questions:
            print("[SUBMIT_QUIZ] ERROR: No questions found")
            return jsonify({'success': False, 'error': 'Quiz not found'}), 404
        
        # Calculate score
        score = 0
        total = len(questions)
        
        for q in questions:
            if str(q['id']) in answers and answers[str(q['id'])] == q['correct_option_index']:
                score += 1
        
        print(f"[SUBMIT_QUIZ] Score calculated: {score}/{total}")
        
        # Save submission
        try:
            submission_id = db.execute_insert(
                'INSERT INTO quiz_submissions (quiz_id, student_id, score, total, answers, duration_seconds) VALUES (?, ?, ?, ?, ?, ?)',
                (quiz_id, get_current_user_id(), score, total, json.dumps(answers), duration)
            )
            print(f"[SUBMIT_QUIZ] Saved to database with ID: {submission_id}")
        except Exception as db_error:
            print(f"[SUBMIT_QUIZ] DATABASE ERROR: {db_error}")
            return jsonify({
                'success': False,
                'error': 'Failed to save submission',
                'message': str(db_error)
            }), 500
        
        # Calculate percentage
        percentage = round((score / total) * 100, 1) if total > 0 else 0
        
        # Try to get adaptive learning insights (OPTIONAL - won't block if fails)
        gaps = []
        recommendations = []
        
        try:
            print("[SUBMIT_QUIZ] Attempting adaptive learning analysis...")
            
            # Get class_id
            quiz = db.execute_one('SELECT class_id FROM quizzes WHERE id = ?', (quiz_id,))
            
            if quiz and quiz.get('class_id'):
                class_id = quiz['class_id']
                
                # Try to update metrics (ignore errors)
                try:
                    adaptive.update_student_metrics(get_current_user_id(), class_id)
                except Exception as e:
                    print(f"[SUBMIT_QUIZ] Metrics update failed (ignored): {e}")
                
                # Try to get gaps (ignore errors)
                try:
                    gaps = adaptive.analyze_knowledge_gaps(get_current_user_id(), class_id) or []
                    print(f"[SUBMIT_QUIZ] Found {len(gaps)} knowledge gaps")
                except Exception as e:
                    print(f"[SUBMIT_QUIZ] Gap analysis failed (ignored): {e}")
                
                # Try to get recommendations (ignore errors)
                try:
                    recommendations = adaptive.generate_recommendations(get_current_user_id(), class_id) or []
                    print(f"[SUBMIT_QUIZ] Generated {len(recommendations)} recommendations")
                except Exception as e:
                    print(f"[SUBMIT_QUIZ] Recommendations failed (ignored): {e}")
            
            print("[SUBMIT_QUIZ] Adaptive analysis completed")
            
        except Exception as adaptive_error:
            print(f"[SUBMIT_QUIZ] Adaptive learning failed (non-blocking): {adaptive_error}")
            # Continue anyway - adaptive features are completely optional
        
        # Build response with adaptive insights
        response = {
            'success': True,
            'message': 'Quiz submitted successfully',
            'score': score,
            'total': total,
            'percentage': percentage,
            'adaptive_insights': {
                'knowledge_gaps_detected': len(gaps),
                'gaps': gaps[:3] if gaps else [],
                'recommendations_generated': len(recommendations),
                'recommendations': recommendations[:5] if recommendations else []
            }
        }
        
        print(f"[SUBMIT_QUIZ] ===== SUCCESS: {score}/{total} ({percentage}%) =====")
        return jsonify(response), 200
        
    except Exception as e:
        print(f"[SUBMIT_QUIZ] ===== FATAL ERROR: {str(e)} =====")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': 'Failed to submit quiz',
            'message': str(e)
        }), 500



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
@login_required
def chatbot():
    """KyKnoX AI chatbot endpoint"""
    data = request.json
    prompt = sanitize_input(data.get('prompt', ''), max_length=2000)
    mode = data.get('mode', 'expert')
    
    if not prompt:
        return jsonify({'error': 'Prompt required'}), 400
    
    # Get student context for personalization
    student_context = adaptive.get_student_context(get_current_user_id())
    
    # Get role from session
    role = session.get('role', 'student')

    # Generate AI response
    answer, provider = kyknox.generate_response(prompt, mode, student_context, role)
    
    # Render markdown
    rendered_answer = kyknox.render_markdown(answer)
    
    # Save to database
    db.execute_insert(
        'INSERT INTO ai_queries (user_id, prompt, response, provider, mode) VALUES (?, ?, ?, ?, ?)',
        (get_current_user_id(), prompt, answer, provider, mode)
    )
    
    return jsonify({
        'answer': rendered_answer,
        'raw': answer,
        'response': rendered_answer,  # For frontend compatibility
        'provider': provider,
        'personalized': bool(student_context.get('weak_topics'))
    }), 200

@app.route('/api/ai/history')
@login_required
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
@login_required
def get_recommendations():
    """Get AI recommendations for student"""
    # Try getting from DB first
    recs = db.execute_query(
        '''SELECT * FROM recommendations 
           WHERE user_id = ? AND is_completed = 0 
           ORDER BY priority DESC, created_at DESC LIMIT 5''',
        (get_current_user_id(),)
    )
    
    # If no recommendations, generate some basic ones using Adaptive Learning
    if not recs:
        # Check for enrolled classes to generate context
        enrolled = db.execute_query(
            'SELECT class_id FROM enrollments WHERE student_id = ? LIMIT 1',
             (get_current_user_id(),)
        )
        if enrolled:
             # Trigger generation (this would normally be async)
             adaptive.generate_recommendations(get_current_user_id(), enrolled[0]['class_id'])
             # Fetch again
             recs = db.execute_query(
                '''SELECT * FROM recommendations 
                   WHERE user_id = ? AND is_completed = 0 
                   ORDER BY priority DESC, created_at DESC LIMIT 5''',
                (get_current_user_id(),)
            )
            
    return jsonify(recs)

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
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

# ============================================================================
# ANALYTICS ROUTES
# ============================================================================

@app.route('/api/student/analytics', methods=['GET'])
@login_required
def get_student_analytics():
    """Get student analytics data"""
    try:
        user_id = get_current_user_id()
        analytics = data_generator.generate_student_analytics(user_id)
        return jsonify(analytics), 200
        
    except Exception as e:
        logger.error(f"Error fetching student analytics: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/student/quiz-history', methods=['GET'])
@login_required
def get_quiz_history():
    """Get paginated quiz history with filters"""
    try:
        user_id = get_current_user_id()
        
        # Get query parameters
        class_filter = request.args.get('class_id', type=int)
        sort_by = request.args.get('sort', 'date')  # date, score, time
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Get analytics data
        analytics = data_generator.generate_student_analytics(user_id)
        attempts = analytics['quiz_attempts']
        
        # Apply class filter
        if class_filter:
            attempts = [a for a in attempts if a['class_id'] == class_filter]
        
        # Apply sorting
        if sort_by == 'score':
            attempts.sort(key=lambda x: x['score_percent'], reverse=True)
        elif sort_by == 'time':
            attempts.sort(key=lambda x: x['time_taken_minutes'])
        else:  # date
            attempts.sort(key=lambda x: x['submitted_at'], reverse=True)
        
        # Paginate
        start = (page - 1) * per_page
        end = start + per_page
        paginated = attempts[start:end]
        
        return jsonify({
            'attempts': paginated,
            'total': len(attempts),
            'page': page,
            'per_page': per_page,
            'total_pages': (len(attempts) + per_page - 1) // per_page
        }), 200
            
    except Exception as e:
        logger.error(f"Error fetching quiz history: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/teacher/analytics', methods=['GET'])
@login_required
def get_teacher_analytics():
    """Get teacher analytics for all classes"""
    try:
        user_id = get_current_user_id()
        analytics = data_generator.generate_teacher_analytics(user_id)
        return jsonify(analytics), 200
        
    except Exception as e:
        logger.error(f"Error fetching teacher analytics: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/teacher/class-stats/<int:class_id>', methods=['GET'])
@login_required
def get_class_stats(class_id):
    """Get detailed stats for a specific class"""
    try:
        user_id = get_current_user_id()
        
        # Get analytics data for all classes, then filter
        analytics = data_generator.generate_teacher_analytics(user_id)
        
        # Find the specific class
        class_stats = None
        for cls in analytics['class_analytics']:
            if cls['class_id'] == class_id:
                class_stats = cls
                break
        
        if not class_stats:
            return jsonify({'error': 'Class not found'}), 404
        
        return jsonify(class_stats), 200
            
    except Exception as e:
        logger.error(f"Error fetching class stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/student/recommendations', methods=['GET'])
@login_required
def get_ai_recommendations():
    """Get AI-powered learning recommendations"""
    try:
        user_id = get_current_user_id()
        analytics = data_generator.generate_student_analytics(user_id)
        
        # Generate recommendations based on performance
        recommendations = []
        
        # Recommendation based on weak topics
        for topic_data in analytics['weak_topics']:
            recommendations.append({
                'id': len(recommendations) + 1,
                'type': 'topic_review',
                'priority': 'high',
                'title': f'Review {topic_data["topic"]}',
                'description': f'Your performance in {topic_data["topic"]} is at {topic_data["score"]}%. We recommend reviewing this topic to strengthen your understanding.',
                'action': 'Review Materials',
                'icon': '📚',
                'estimated_time': '30-45 minutes'
            })
        
        # Recommendation for practice
        if analytics['avg_score'] < 80:
            recommendations.append({
                'id': len(recommendations) + 1,
                'type': 'practice',
                'priority': 'medium',
                'title': 'Take More Practice Quizzes',
                'description': f'Your average score is {analytics["avg_score"]}%. Regular practice can help improve your performance.',
                'action': 'Browse Quizzes',
                'icon': '✍️',
                'estimated_time': '20-30 minutes'
            })
        
        # Recommendation for strong topics
        if analytics['strong_topics']:
            best_topic = analytics['strong_topics'][0]
            recommendations.append({
                'id': len(recommendations) + 1,
                'type': 'advancement',
                'priority': 'low',
                'title': f'Advance in {best_topic["topic"]}',
                'description': f'You\'re excelling in {best_topic["topic"]} with {best_topic["score"]}%! Consider exploring advanced topics in this area.',
                'action': 'Explore Advanced',
                'icon': '🚀',
                'estimated_time': '45-60 minutes'
            })
        
        # Study consistency recommendation
        if analytics['streak_days'] < 3:
            recommendations.append({
                'id': len(recommendations) + 1,
                'type': 'consistency',
                'priority': 'medium',
                'title': 'Build a Study Streak',
                'description': 'Consistent daily practice leads to better retention. Try to study for at least 15 minutes every day.',
                'action': 'Start Today',
                'icon': '🔥',
                'estimated_time': '15 minutes daily'
            })
        
        return jsonify({'recommendations': recommendations}), 200
        
    except Exception as e:
        logger.error(f"Error fetching recommendations: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/student/knowledge-gaps', methods=['GET'])
@login_required
def get_knowledge_gaps():
    """Get identified knowledge gaps"""
    try:
        user_id = get_current_user_id()
        analytics = data_generator.generate_student_analytics(user_id)
        
        # Generate knowledge gaps based on weak topics
        gaps = []
        
        for topic_data in analytics['weak_topics']:
            gap_severity = 'critical' if topic_data['score'] < 50 else 'moderate' if topic_data['score'] < 70 else 'minor'
            
            gaps.append({
                'id': len(gaps) + 1,
                'topic': topic_data['topic'],
                'score': topic_data['score'],
                'severity': gap_severity,
                'questions_attempted': topic_data['attempts'],
                'common_mistakes': [
                    f'Difficulty with fundamental concepts in {topic_data["topic"]}',
                    f'Need more practice with {topic_data["topic"]} applications',
                    f'Review recommended for {topic_data["topic"]} theory'
                ],
                'recommended_resources': [
                    {'type': 'video', 'title': f'{topic_data["topic"]} Fundamentals', 'duration': '15 min'},
                    {'type': 'practice', 'title': f'{topic_data["topic"]} Practice Set', 'questions': 10},
                    {'type': 'reading', 'title': f'{topic_data["topic"]} Study Guide', 'pages': 8}
                ],
                'improvement_plan': f'Focus on {topic_data["topic"]} basics, complete practice exercises, and review key concepts daily for one week.'
            })
        
        # Add a general gap if overall performance is low
        if analytics['avg_score'] < 75:
            gaps.append({
                'id': len(gaps) + 1,
                'topic': 'Time Management',
                'score': 0,
                'severity': 'moderate',
                'questions_attempted': 0,
                'common_mistakes': [
                    'Rushing through questions',
                    'Not reading questions carefully',
                    'Insufficient time for review'
                ],
                'recommended_resources': [
                    {'type': 'guide', 'title': 'Effective Quiz-Taking Strategies', 'duration': '10 min'},
                    {'type': 'practice', 'title': 'Timed Practice Sessions', 'questions': 15}
                ],
                'improvement_plan': 'Practice with timed quizzes to improve pacing and accuracy under time constraints.'
            })
        
        return jsonify({'gaps': gaps}), 200
        
    except Exception as e:
        logger.error(f"Error fetching knowledge gaps: {e}")
        return jsonify({'error': str(e)}), 500


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
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Initialize database
    initialize_database()
    
    # Run server
    port = int(os.getenv('PORT', 5000))
    logger.info(f"Starting LearnVaultX server on port {port}")
    
    # Print localhost URL clearly
    print("\n" + "="*60)
    print(f"🚀 LearnVaultX is running!")
    print(f"📍 Open in browser: http://127.0.0.1:{port}")
    print(f"📍 Or use: http://localhost:{port}")
    print("="*60 + "\n")
    
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
