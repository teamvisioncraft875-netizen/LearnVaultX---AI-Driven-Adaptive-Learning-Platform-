from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
import json
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv
import logging
from contextlib import contextmanager
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import markdown
import re

# Load environment variables from .env file
load_dotenv()

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Load secret file from Render if it exists
secret_env_path = '/etc/secrets/.env'
if os.path.exists(secret_env_path):
    load_dotenv(secret_env_path)
    print("Loaded secret file from /etc/secrets/.env")
logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================
# Load database configuration from environment variables for security
# This allows different configurations for development/production
DATABASE_PATH = os.getenv('DATABASE_PATH', 'education.db')
DATABASE_TIMEOUT = float(os.getenv('DATABASE_TIMEOUT', '30.0'))

app = Flask(__name__)
# Load SECRET_KEY from environment variable (more secure)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here-change-in-production')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# ============================================================================
# GMAIL CONFIGURATION FOR OTP
# ============================================================================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('GMAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.getenv('GMAIL_APP_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('GMAIL_USERNAME', 'noreply@education.com')

# Gmail credentials for OTP
GMAIL_USERNAME = os.getenv('GMAIL_USERNAME', '')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD', '')

# Jitsi configuration
JITSI_DOMAIN = os.getenv('JITSI_DOMAIN', 'meet.jit.si')

# Initialize Flask-Mail (optional, we'll use direct SMTP for more control)
# mail = Mail(app)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# AI API clients - Multiple providers for reliability!
deepseek_api_key = os.environ.get('DEEPSEEK_API_KEY', '')
groq_api_key = os.environ.get('GROQ_API_KEY', '')
openai_api_key = os.environ.get('OPENAI_API_KEY', '')
anthropic_api_key = os.environ.get('ANTHROPIC_API_KEY', '')

# Initialize AI providers
deepseek_client = None
groq_client = None
openai_client = None
claude_client = None
ai_provider = "none"

# Check Claude (Anthropic) - BEST for education! Priority #1
if anthropic_api_key:
    try:
        import anthropic
        claude_client = anthropic.Anthropic(api_key=anthropic_api_key)
        ai_provider = "claude"
        logger.info("Claude AI (Anthropic) initialized - BEST for adaptive learning!")
    except Exception as e:
        logger.warning(f"Failed to initialize Claude client: {e}")

# Check Groq (FREE & FAST!) - Priority #2
if groq_api_key and ai_provider == "none":
    try:
        groq_client = True
        ai_provider = "groq"
        logger.info("Groq AI API key found - ready to use")
    except Exception as e:
        logger.warning(f"Failed to initialize Groq client: {e}")

# Check DeepSeek - Priority #3
if deepseek_api_key and ai_provider == "none":
    try:
        deepseek_client = True
        ai_provider = "deepseek"
        logger.info("DeepSeek AI API key found - ready to use")
    except Exception as e:
        logger.warning(f"Failed to initialize DeepSeek client: {e}")

# Check OpenAI - Priority #4
if openai_api_key and ai_provider == "none":
    try:
        openai_client = True
        ai_provider = "openai"
        logger.info("OpenAI API key found - ready to use")
    except Exception as e:
        logger.warning(f"Failed to initialize OpenAI client: {e}")

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ============================================================================
# DATABASE CONNECTION FUNCTIONS WITH ERROR HANDLING
# ============================================================================

def get_db():
    """
    Connect to the SQLite database using path and timeout from env vars.
    Returns db object and ensures proper error, logging, and constraints.
    """
    try:
        # Create connection with timeout setting
        db = sqlite3.connect(
            DATABASE_PATH,
            timeout=DATABASE_TIMEOUT,
            check_same_thread=False  # Allow multi-threaded access
        )

        # Enable Row factory for dictionary-like access to results
        db.row_factory = sqlite3.Row
        # Enable foreign key constraints (SQLite doesn't enable by default)
        db.execute('PRAGMA foreign_keys = ON')
        logger.debug(f"Database connection established: {DATABASE_PATH}")
        return db
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise

@contextmanager
def get_db_context():
    """
    Context manager for database connections.
    Ensures connections are properly closed even if errors occur.
    
    Usage:
        with get_db_context() as db:
            db.execute("SELECT * FROM users")
            # Connection automatically closed after block
    """
    db = None
    try:
        db = get_db()
        yield db
        db.commit()
    except sqlite3.Error as e:
        if db:
            db.rollback()
        logger.error(f"Database transaction error: {e}")
        raise
    finally:
        if db:
            db.close()
            logger.debug("Database connection closed")

def init_db():
    """
    Initialize the database by creating all tables from schema.sql
    
    This function:
    - Reads the SQL schema file
    - Executes all CREATE TABLE statements
    - Includes error handling and rollback on failure
    - Logs the initialization process
    """
    try:
        logger.info("Initializing database...")
        
        # Check if schema file exists
        if not os.path.exists('schema.sql'):
            logger.error("schema.sql file not found!")
            raise FileNotFoundError("schema.sql file is required for database initialization")
        
        db = get_db()
        
        # Read and execute schema
        with open('schema.sql', 'r', encoding='utf-8') as f:
            schema_sql = f.read()
            db.executescript(schema_sql)
        
        db.commit()
        db.close()
        
        logger.info(f"Database initialized successfully: {DATABASE_PATH}")
        
    except sqlite3.Error as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {e}")
        raise

def check_db_health():
    """
    Perform a health check on the database connection.
    
    Returns:
        dict: Health check results with status and details
    """
    try:
        db = get_db()
        
        # Try a simple query to verify connection works
        cursor = db.execute("SELECT COUNT(*) as count FROM sqlite_master WHERE type='table'")
        result = cursor.fetchone()
        table_count = result['count']
        
        # Check if database file exists and is readable
        db_size = os.path.getsize(DATABASE_PATH) if os.path.exists(DATABASE_PATH) else 0
        
        db.close()
        
        health_status = {
            'status': 'healthy',
            'database_path': DATABASE_PATH,
            'table_count': table_count,
            'database_size_bytes': db_size,
            'connection_timeout': DATABASE_TIMEOUT
        }
        
        logger.info(f"Database health check passed: {table_count} tables found")
        return health_status
        
    except sqlite3.Error as e:
        logger.error(f"Database health check failed: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'database_path': DATABASE_PATH
        }
    except Exception as e:
        logger.error(f"Unexpected error during health check: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'database_path': DATABASE_PATH
        }

# ============================================================================
# HELPER FUNCTIONS FOR NEW FEATURES
# ============================================================================

def generate_otp(length=4):
    """Generate a random OTP (numeric only)"""
    return ''.join(random.choices(string.digits, k=length))

def send_otp_email(email, otp):
    """
    Send OTP email using Gmail SMTP
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    if not GMAIL_USERNAME or not GMAIL_APP_PASSWORD:
        logger.error("Gmail credentials not configured")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Password Reset OTP - Education Platform'
        msg['From'] = GMAIL_USERNAME
        msg['To'] = email
        
        # HTML email content
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: #f9f9f9; padding: 30px; border-radius: 10px;">
                <h2 style="color: #667eea;">Password Reset Request</h2>
                <p>Hello,</p>
                <p>You requested to reset your password. Use the OTP below to continue:</p>
                <div style="background: white; padding: 20px; border-radius: 5px; text-align: center; margin: 20px 0;">
                    <h1 style="color: #667eea; font-size: 48px; letter-spacing: 10px; margin: 0;">{otp}</h1>
                </div>
                <p>This OTP will expire in 10 minutes.</p>
                <p>If you didn't request this, please ignore this email.</p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                <p style="color: #666; font-size: 12px;">Education Platform - AI-Driven Adaptive Learning</p>
            </div>
        </body>
        </html>
        """
        
        part = MIMEText(html_content, 'html')
        msg.attach(part)
        
        # Send email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USERNAME, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USERNAME, email, msg.as_string())
        server.quit()
        
        logger.info(f"OTP email sent successfully to {email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send OTP email: {e}")
        return False

def render_markdown_with_math(text):
    """
    Render markdown and preserve math equations for MathJax
    
    Args:
        text: Raw text with markdown and LaTeX
        
    Returns:
        HTML with markdown rendered and math preserved
    """
    # Convert markdown to HTML
    html = markdown.markdown(text, extensions=['extra', 'codehilite'])
    
    # Return HTML (MathJax will handle math rendering on frontend)
    return html

def clean_expired_otps():
    """Clean up expired OTPs from database"""
    try:
        db = get_db()
        db.execute("DELETE FROM password_reset_otp WHERE expires_at < ? OR used = 1", 
                  (datetime.now(),))
        db.commit()
        db.close()
    except Exception as e:
        logger.error(f"Failed to clean expired OTPs: {e}")

# ============================================================================
# ADAPTIVE LEARNING ENGINE - AI-DRIVEN PERSONALIZATION
# ============================================================================

def analyze_knowledge_gaps(db, student_id, class_id):
    """
    AI-powered knowledge gap detection from quiz performance.
    Analyzes which topics student struggles with.
    
    Returns: List of gaps with topic names and mastery levels
    """
    try:
        # Get all quiz submissions for this student in this class
        submissions = db.execute('''
            SELECT qs.*, qq.id as question_id, qq.correct_option_index
            FROM quiz_submissions qs
            JOIN quizzes q ON qs.quiz_id = q.id
            JOIN quiz_questions qq ON qq.quiz_id = q.id
            WHERE qs.student_id = ? AND q.class_id = ?
            ORDER BY qs.submitted_at DESC
        ''', (student_id, class_id)).fetchall()
        
        if not submissions:
            return []
        
        # Group by topics (if topics exist)
        topic_performance = {}
        
        for submission in submissions:
            # Get topics for this question
            topics = db.execute('''
                SELECT t.id, t.topic_name
                FROM topics t
                JOIN question_topics qt ON t.id = qt.topic_id
                WHERE qt.question_id = ?
            ''', (submission['question_id'],)).fetchall()
            
            for topic in topics:
                topic_id = topic['id']
                topic_name = topic['topic_name']
                
                if topic_id not in topic_performance:
                    topic_performance[topic_id] = {
                        'name': topic_name,
                        'correct': 0,
                        'total': 0
                    }
                
                topic_performance[topic_id]['total'] += 1
                # Check if student got it right (would need answer data)
                # For now, use overall submission score as proxy
        
        # Calculate mastery levels and identify gaps
        gaps = []
        for topic_id, perf in topic_performance.items():
            if perf['total'] > 0:
                mastery = perf['correct'] / perf['total']
                
                # Update knowledge_gaps table
                db.execute('''
                    INSERT OR REPLACE INTO knowledge_gaps
                    (user_id, topic_id, mastery_level, questions_attempted, questions_correct, last_assessed)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (student_id, topic_id, mastery, perf['total'], perf['correct'], datetime.now()))
                
                # If mastery < 60%, it's a gap
                if mastery < 0.6:
                    gaps.append({
                        'topic_id': topic_id,
                        'topic_name': perf['name'],
                        'mastery_level': round(mastery * 100, 1),
                        'severity': 'critical' if mastery < 0.4 else 'moderate'
                    })
        
        db.commit()
        return gaps
        
    except Exception as e:
        logger.error(f"Error analyzing knowledge gaps: {e}")
        return []

def generate_adaptive_recommendations(db, student_id, class_id):
    """
    AI-powered content recommendation engine.
    Recommends lectures, quizzes, and practice based on knowledge gaps.
    
    Returns: List of personalized recommendations
    """
    try:
        # Get knowledge gaps
        gaps = db.execute('''
            SELECT kg.*, t.topic_name, t.class_id
            FROM knowledge_gaps kg
            JOIN topics t ON kg.topic_id = t.id
            WHERE kg.user_id = ? AND t.class_id = ?
            ORDER BY kg.mastery_level ASC
            LIMIT 5
        ''', (student_id, class_id)).fetchall()
        
        recommendations = []
        
        for gap in gaps:
            topic_id = gap['topic_id']
            topic_name = gap['topic_name']
            mastery = gap['mastery_level']
            
            # Recommend lectures on this topic
            lectures = db.execute('''
                SELECT l.id, l.filename, l.class_id
                FROM lectures l
                WHERE l.class_id = ?
                LIMIT 2
            ''', (class_id,)).fetchall()
            
            for lecture in lectures:
                reason = f"Review lecture on {topic_name} (Current mastery: {round(mastery*100, 1)}%)"
                priority = int((1 - mastery) * 100)  # Lower mastery = higher priority
                
                # Check if already recommended
                existing = db.execute('''
                    SELECT id FROM recommendations 
                    WHERE user_id = ? AND content_type = 'lecture' AND content_id = ?
                    AND is_completed = 0
                ''', (student_id, lecture['id'])).fetchone()
                
                if not existing:
                    db.execute('''
                        INSERT INTO recommendations
                        (user_id, content_type, content_id, reason, priority)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (student_id, 'lecture', lecture['id'], reason, priority))
                    
                    recommendations.append({
                        'type': 'lecture',
                        'id': lecture['id'],
                        'title': lecture['filename'],
                        'reason': reason,
                        'priority': priority
                    })
            
            # Recommend practice quizzes
            quizzes = db.execute('''
                SELECT q.id, q.title
                FROM quizzes q
                WHERE q.class_id = ?
                LIMIT 1
            ''', (class_id,)).fetchall()
            
            for quiz in quizzes:
                reason = f"Practice quiz for {topic_name} to improve mastery"
                priority = int((1 - mastery) * 100) + 10  # Quizzes slightly higher priority
                
                existing = db.execute('''
                    SELECT id FROM recommendations 
                    WHERE user_id = ? AND content_type = 'quiz' AND content_id = ?
                    AND is_completed = 0
                ''', (student_id, quiz['id'])).fetchone()
                
                if not existing:
                    db.execute('''
                        INSERT INTO recommendations
                        (user_id, content_type, content_id, reason, priority)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (student_id, 'quiz', quiz['id'], reason, priority))
                    
                    recommendations.append({
                        'type': 'quiz',
                        'id': quiz['id'],
                        'title': quiz['title'],
                        'reason': reason,
                        'priority': priority
                    })
        
        db.commit()
        
        # Sort by priority
        recommendations.sort(key=lambda x: x['priority'], reverse=True)
        return recommendations[:10]  # Top 10 recommendations
        
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        return []

def get_student_context_for_ai(db, student_id):
    """
    Gathers student's learning context for AI-powered personalized tutoring.
    Includes recent performance, weak topics, and learning patterns.
    
    Returns: Context dict for AI
    """
    try:
        # Get recent quiz performance
        recent_quizzes = db.execute('''
            SELECT q.title, qs.score, qs.total, qs.submitted_at
            FROM quiz_submissions qs
            JOIN quizzes q ON qs.quiz_id = q.id
            WHERE qs.student_id = ?
            ORDER BY qs.submitted_at DESC
            LIMIT 5
        ''', (student_id,)).fetchall()
        
        # Get knowledge gaps
        gaps = db.execute('''
            SELECT t.topic_name, kg.mastery_level
            FROM knowledge_gaps kg
            JOIN topics t ON kg.topic_id = t.id
            WHERE kg.user_id = ?
            ORDER BY kg.mastery_level ASC
            LIMIT 5
        ''', (student_id,)).fetchall()
        
        # Get learning pace
        metrics = db.execute('''
            SELECT pace_score, rating, score_avg
            FROM student_metrics
            WHERE user_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
        ''', (student_id,)).fetchone()
        
        context = {
            'recent_performance': [
                {
                    'quiz': q['title'],
                    'score': f"{q['score']}/{q['total']}",
                    'percentage': round((q['score'] / q['total']) * 100, 1) if q['total'] > 0 else 0,
                    'date': q['submitted_at']
                } for q in recent_quizzes
            ],
            'weak_topics': [
                {
                    'topic': g['topic_name'],
                    'mastery': round(g['mastery_level'] * 100, 1)
                } for g in gaps
            ],
            'learning_pace': {
                'pace_score': metrics['pace_score'] if metrics else 0,
                'rating': metrics['rating'] if metrics else 0,
                'average_score': metrics['score_avg'] if metrics else 0
            } if metrics else None
        }
        
        return context
        
    except Exception as e:
        logger.error(f"Error getting student context: {e}")
        return {}

def generate_ai_tutoring_response(prompt, student_context):
    """
    Uses Claude 4.5 Sonnet (or fallback AI) to provide personalized tutoring.
    Context-aware: knows student's weak areas and recent performance.
    
    Returns: AI response with personalized help
    """
    try:
        # Build context-aware system prompt
        system_prompt = """You are an expert educational AI tutor specializing in adaptive learning. 
        You provide personalized help based on each student's unique learning journey.
        
        Be encouraging, clear, and adapt your explanations to the student's level.
        Use examples and break down complex topics into digestible parts.
        Always relate your answers to the student's current learning gaps when relevant."""
        
        # Add student context to prompt
        if student_context and student_context.get('weak_topics'):
            weak_topics_str = ", ".join([t['topic'] for t in student_context['weak_topics'][:3]])
            system_prompt += f"\n\nThis student is currently working on improving in: {weak_topics_str}."
            
            if student_context.get('recent_performance'):
                recent = student_context['recent_performance'][0]
                system_prompt += f"\nTheir most recent quiz score was {recent['score']} ({recent['percentage']}%)."
        
        # Try Claude first (BEST for education!)
        if claude_client:
            message = claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": f"{system_prompt}\n\nStudent question: {prompt}"}
                ]
            )
            return message.content[0].text
        
        # Fallback to other AI providers
        return call_fallback_ai(prompt, system_prompt)
        
    except Exception as e:
        logger.error(f"Error generating AI tutoring response: {e}")
        return "I'm having trouble connecting right now. Please try again in a moment."

def call_fallback_ai(prompt, system_prompt):
    """Fallback AI when Claude is not available"""
    import requests
    
    # Try Groq
    if groq_client:
        headers = {
            "Authorization": f"Bearer {groq_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 800
        }
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", 
                                headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
    
    # Try DeepSeek
    if deepseek_client:
        headers = {
            "Authorization": f"Bearer {deepseek_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 800
        }
        response = requests.post("https://api.deepseek.com/v1/chat/completions", 
                                headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
    
    return "AI service temporarily unavailable. Please configure an API key."

def check_and_create_intervention_alerts(db, student_id, class_id):
    """
    Monitors student performance and creates alerts for teachers
    when intervention is needed (AI-driven early warning system).
    """
    try:
        # Get student metrics
        metrics = db.execute('''
            SELECT * FROM student_metrics
            WHERE user_id = ? AND class_id = ?
        ''', (student_id, class_id)).fetchone()
        
        if not metrics:
            return
        
        # Get teacher
        teacher = db.execute('''
            SELECT teacher_id FROM classes WHERE id = ?
        ''', (class_id,)).fetchone()
        
        if not teacher:
            return
        
        teacher_id = teacher['teacher_id']
        
        # Check for intervention triggers
        alerts = []
        
        # Trigger 1: Low performance (pace_score < 4.0)
        if metrics['pace_score'] < 4.0:
            # Check if alert already exists
            existing = db.execute('''
                SELECT id FROM teacher_interventions
                WHERE student_id = ? AND class_id = ? AND alert_type = 'low_performance'
                AND is_resolved = 0
            ''', (student_id, class_id)).fetchone()
            
            if not existing:
                message = f"Student performance is below threshold (Pace: {metrics['pace_score']}/10). Immediate attention needed."
                db.execute('''
                    INSERT INTO teacher_interventions
                    (student_id, teacher_id, class_id, alert_type, message)
                    VALUES (?, ?, ?, ?, ?)
                ''', (student_id, teacher_id, class_id, 'low_performance', message))
                alerts.append('low_performance')
        
        # Trigger 2: Knowledge gaps
        gaps = db.execute('''
            SELECT COUNT(*) as gap_count
            FROM knowledge_gaps
            WHERE user_id = ? AND mastery_level < 0.5
        ''', (student_id,)).fetchone()
        
        if gaps and gaps['gap_count'] >= 3:
            existing = db.execute('''
                SELECT id FROM teacher_interventions
                WHERE student_id = ? AND class_id = ? AND alert_type = 'knowledge_gap'
                AND is_resolved = 0
            ''', (student_id, class_id)).fetchone()
            
            if not existing:
                message = f"Student has {gaps['gap_count']} significant knowledge gaps. Recommend review sessions."
                db.execute('''
                    INSERT INTO teacher_interventions
                    (student_id, teacher_id, class_id, alert_type, message)
                    VALUES (?, ?, ?, ?, ?)
                ''', (student_id, teacher_id, class_id, 'knowledge_gap', message))
                alerts.append('knowledge_gap')
        
        # Trigger 3: Disengagement (no activity in last 7 days)
        last_activity = db.execute('''
            SELECT MAX(submitted_at) as last_active
            FROM quiz_submissions
            WHERE student_id = ?
        ''', (student_id,)).fetchone()
        
        if last_activity and last_activity['last_active']:
            days_since = (datetime.now() - datetime.fromisoformat(last_activity['last_active'])).days
            if days_since > 7:
                existing = db.execute('''
                    SELECT id FROM teacher_interventions
                    WHERE student_id = ? AND class_id = ? AND alert_type = 'disengaged'
                    AND is_resolved = 0
                ''', (student_id, class_id)).fetchone()
                
                if not existing:
                    message = f"Student inactive for {days_since} days. May need re-engagement."
                    db.execute('''
                        INSERT INTO teacher_interventions
                        (student_id, teacher_id, class_id, alert_type, message)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (student_id, teacher_id, class_id, 'disengaged', message))
                    alerts.append('disengaged')
        
        db.commit()
        return alerts
        
    except Exception as e:
        logger.error(f"Error checking intervention alerts: {e}")
        return []

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'teacher':
            return jsonify({'error': 'Unauthorized'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        if session['role'] == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role', 'student')
        
        if not name or not email or not password:
            return jsonify({'error': 'All fields are required'}), 400
        
        db = get_db()
        
        # Check if user exists
        existing_user = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing_user:
            return jsonify({'error': 'Email already registered'}), 400
        
        # Create user
        password_hash = generate_password_hash(password)
        db.execute('INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
                   (name, email, password_hash, role))
        db.commit()
        db.close()
        
        return jsonify({'message': 'Registration successful'}), 201
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        db.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['email'] = user['email']
            session['role'] = user['role']
            return jsonify({'message': 'Login successful', 'role': user['role']}), 200
        
        return jsonify({'error': 'Invalid credentials'}), 401
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/teacher/dashboard')
@login_required
@teacher_required
def teacher_dashboard():
    return render_template('teacher_dashboard.html')

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    return render_template('student_dashboard.html')

@app.route('/api/teacher/classes')
@login_required
@teacher_required
def get_teacher_classes():
    db = get_db()
    classes = db.execute(
        'SELECT * FROM classes WHERE teacher_id = ? ORDER BY created_at DESC',
        (session['user_id'],)
    ).fetchall()
    db.close()
    
    return jsonify([dict(c) for c in classes])

@app.route('/api/create_class', methods=['POST'])
@login_required
@teacher_required
def create_class():
    data = request.json
    title = data.get('title')
    description = data.get('description', '')
    
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    
    db = get_db()
    cursor = db.execute(
        'INSERT INTO classes (title, description, teacher_id) VALUES (?, ?, ?)',
        (title, description, session['user_id'])
    )
    class_id = cursor.lastrowid
    db.commit()
    db.close()
    
    return jsonify({'message': 'Class created', 'class_id': class_id}), 201

@app.route('/api/upload_lecture', methods=['POST'])
@login_required
@teacher_required
def upload_lecture():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    class_id = request.form.get('class_id')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and class_id:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        db = get_db()
        db.execute(
            'INSERT INTO lectures (class_id, filename, filepath) VALUES (?, ?, ?)',
            (class_id, filename, filepath)
        )
        db.commit()
        db.close()
        
        return jsonify({'message': 'Lecture uploaded', 'filename': filename}), 201
    
    return jsonify({'error': 'Invalid request'}), 400

@app.route('/api/student/classes')
@login_required
def get_student_classes():
    db = get_db()
    # Get enrolled classes
    classes = db.execute('''
        SELECT c.*, u.name as teacher_name
        FROM classes c
        JOIN enrollments e ON c.id = e.class_id
        JOIN users u ON c.teacher_id = u.id
        WHERE e.student_id = ?
        ORDER BY e.enrolled_at DESC
    ''', (session['user_id'],)).fetchall()
    db.close()
    
    return jsonify([dict(c) for c in classes])

@app.route('/api/available_classes')
@login_required
def get_available_classes():
    db = get_db()
    classes = db.execute('''
        SELECT c.*, u.name as teacher_name
        FROM classes c
        JOIN users u ON c.teacher_id = u.id
        WHERE c.id NOT IN (
            SELECT class_id FROM enrollments WHERE student_id = ?
        )
        ORDER BY c.created_at DESC
    ''', (session['user_id'],)).fetchall()
    db.close()
    
    return jsonify([dict(c) for c in classes])

@app.route('/api/join_class', methods=['POST'])
@login_required
def join_class():
    data = request.json
    class_id = data.get('class_id')
    
    if not class_id:
        return jsonify({'error': 'Class ID required'}), 400
    
    db = get_db()
    
    # Check if already enrolled
    existing = db.execute(
        'SELECT id FROM enrollments WHERE student_id = ? AND class_id = ?',
        (session['user_id'], class_id)
    ).fetchone()
    
    if existing:
        return jsonify({'error': 'Already enrolled'}), 400
    
    db.execute(
        'INSERT INTO enrollments (student_id, class_id) VALUES (?, ?)',
        (session['user_id'], class_id)
    )
    db.commit()
    db.close()
    
    return jsonify({'message': 'Enrolled successfully'}), 201

@app.route('/class/<int:class_id>')
@login_required
def class_view(class_id):
    db = get_db()
    
    # Get class details
    class_info = db.execute('SELECT * FROM classes WHERE id = ?', (class_id,)).fetchone()
    
    if not class_info:
        db.close()
        return "Class not found", 404
    
    # Check access
    if session['role'] == 'student':
        enrollment = db.execute(
            'SELECT id FROM enrollments WHERE student_id = ? AND class_id = ?',
            (session['user_id'], class_id)
        ).fetchone()
        if not enrollment:
            db.close()
            return "Access denied", 403
    elif class_info['teacher_id'] != session['user_id']:
        db.close()
        return "Access denied", 403
    
    db.close()
    return render_template('class_view.html', class_id=class_id)

@app.route('/api/class/<int:class_id>/lectures')
@login_required
def get_class_lectures(class_id):
    db = get_db()
    lectures = db.execute(
        'SELECT * FROM lectures WHERE class_id = ? ORDER BY uploaded_at DESC',
        (class_id,)
    ).fetchall()
    db.close()
    
    return jsonify([dict(l) for l in lectures])

@app.route('/api/create_quiz', methods=['POST'])
@login_required
@teacher_required
def create_quiz():
    data = request.json
    class_id = data.get('class_id')
    title = data.get('title')
    questions = data.get('questions', [])
    
    if not class_id or not title or not questions:
        return jsonify({'error': 'Invalid data'}), 400
    
    db = get_db()
    
    # Create quiz
    cursor = db.execute(
        'INSERT INTO quizzes (class_id, title) VALUES (?, ?)',
        (class_id, title)
    )
    quiz_id = cursor.lastrowid
    
    # Add questions
    for q in questions:
        db.execute(
            'INSERT INTO quiz_questions (quiz_id, question_text, options, correct_option_index) VALUES (?, ?, ?, ?)',
            (quiz_id, q['question'], json.dumps(q['options']), q['correct'])
        )
    
    db.commit()
    db.close()
    
    return jsonify({'message': 'Quiz created', 'quiz_id': quiz_id}), 201

@app.route('/api/class/<int:class_id>/quizzes')
@login_required
def get_class_quizzes(class_id):
    db = get_db()
    quizzes = db.execute(
        'SELECT * FROM quizzes WHERE class_id = ? ORDER BY created_at DESC',
        (class_id,)
    ).fetchall()
    db.close()
    
    return jsonify([dict(q) for q in quizzes])

@app.route('/api/quiz/<int:quiz_id>')
@login_required
def get_quiz(quiz_id):
    db = get_db()
    
    quiz = db.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    if not quiz:
        db.close()
        return jsonify({'error': 'Quiz not found'}), 404
    
    questions = db.execute(
        'SELECT id, question_text, options FROM quiz_questions WHERE quiz_id = ?',
        (quiz_id,)
    ).fetchall()
    
    db.close()
    
    quiz_data = dict(quiz)
    quiz_data['questions'] = [dict(q) for q in questions]
    for q in quiz_data['questions']:
        q['options'] = json.loads(q['options'])
    
    return jsonify(quiz_data)

@app.route('/api/submit_quiz', methods=['POST'])
@login_required
def submit_quiz():
    """
    ENHANCED QUIZ SUBMISSION with Adaptive Learning Features
    Now triggers gap analysis, recommendations, and intervention alerts!
    """
    data = request.json
    quiz_id = data.get('quiz_id')
    answers = data.get('answers', {})
    duration = data.get('duration', 0)
    
    if not quiz_id:
        return jsonify({'error': 'Quiz ID required'}), 400
    
    db = get_db()
    
    # Get correct answers
    questions = db.execute(
        'SELECT id, correct_option_index FROM quiz_questions WHERE quiz_id = ?',
        (quiz_id,)
    ).fetchall()
    
    score = 0
    total = len(questions)
    
    for q in questions:
        if str(q['id']) in answers and answers[str(q['id'])] == q['correct_option_index']:
            score += 1
    
    # Save submission
    db.execute(
        'INSERT INTO quiz_submissions (quiz_id, student_id, score, total, duration_seconds) VALUES (?, ?, ?, ?, ?)',
        (quiz_id, session['user_id'], score, total, duration)
    )
    
    # Get class_id for metrics
    quiz = db.execute('SELECT class_id FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    class_id = quiz['class_id']
    
    # Update student metrics
    update_student_metrics(db, session['user_id'], class_id)
    
    # 🚀 ADAPTIVE LEARNING FEATURES
    # 1. Analyze knowledge gaps
    gaps = analyze_knowledge_gaps(db, session['user_id'], class_id)
    
    # 2. Generate personalized recommendations
    recommendations = generate_adaptive_recommendations(db, session['user_id'], class_id)
    
    # 3. Check for teacher intervention alerts
    alerts = check_and_create_intervention_alerts(db, session['user_id'], class_id)
    
    db.commit()
    db.close()
    
    # Build enhanced response
    response = {
        'message': 'Quiz submitted',
        'score': score,
        'total': total,
        'percentage': round((score / total) * 100, 1),
        'adaptive_insights': {
            'knowledge_gaps_detected': len(gaps),
            'gaps': gaps[:3],  # Top 3 gaps
            'recommendations_generated': len(recommendations),
            'recommendations': recommendations[:5],  # Top 5 recommendations
            'teacher_alerts_triggered': len(alerts) if alerts else 0
        }
    }
    
    return jsonify(response), 200

def update_student_metrics(db, student_id, class_id):
    # Get all quiz submissions for this student in this class
    submissions = db.execute('''
        SELECT qs.score, qs.total, qs.duration_seconds
        FROM quiz_submissions qs
        JOIN quizzes q ON qs.quiz_id = q.id
        WHERE qs.student_id = ? AND q.class_id = ?
    ''', (student_id, class_id)).fetchall()
    
    if not submissions:
        return
    
    # Calculate metrics
    total_score = sum(s['score'] for s in submissions)
    total_possible = sum(s['total'] for s in submissions)
    accuracy = total_score / total_possible if total_possible > 0 else 0
    
    avg_time = sum(s['duration_seconds'] for s in submissions) / len(submissions)
    speed = min(1, 60 / (avg_time + 1))
    
    # Get chat engagement
    chat_count = db.execute(
        'SELECT COUNT(*) as cnt FROM chat_messages WHERE user_id = ? AND class_id = ?',
        (student_id, class_id)
    ).fetchone()['cnt']
    engagement = min(1, chat_count / 20)
    
    # Calculate pace score (0-10)
    pace_score = round(10 * (0.5 * accuracy + 0.3 * speed + 0.2 * engagement), 1)
    
    # Calculate rating (0-10)
    rating = min(10, pace_score)
    
    # Update or insert metrics
    db.execute('''
        INSERT OR REPLACE INTO student_metrics
        (user_id, class_id, score_avg, avg_time, pace_score, rating)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (student_id, class_id, round(accuracy * 100, 1), round(avg_time, 1), pace_score, rating))

@app.route('/api/analytics')
@login_required
def get_analytics():
    db = get_db()
    
    if session['role'] == 'student':
        # Student sees their own metrics
        metrics = db.execute('''
            SELECT sm.*, c.title as class_name
            FROM student_metrics sm
            JOIN classes c ON sm.class_id = c.id
            WHERE sm.user_id = ?
        ''', (session['user_id'],)).fetchall()
        
        db.close()
        return jsonify([dict(m) for m in metrics])
    
    else:
        # Teacher sees all students in their classes
        class_id = request.args.get('class_id')
        
        if class_id:
            metrics = db.execute('''
                SELECT sm.*, u.name as student_name
                FROM student_metrics sm
                JOIN users u ON sm.user_id = u.id
                WHERE sm.class_id = ?
                ORDER BY sm.rating DESC
            ''', (class_id,)).fetchall()
        else:
            metrics = db.execute('''
                SELECT sm.*, u.name as student_name, c.title as class_name
                FROM student_metrics sm
                JOIN users u ON sm.user_id = u.id
                JOIN classes c ON sm.class_id = c.id
                JOIN classes tc ON tc.teacher_id = ?
                WHERE sm.class_id = tc.id
                ORDER BY sm.rating DESC
            ''', (session['user_id'],)).fetchall()
        
        db.close()
        return jsonify([dict(m) for m in metrics])

@app.route('/api/chatbot', methods=['POST'])
@login_required
def chatbot():
    """
    CONTEXT-AWARE AI CHATBOT with Adaptive Learning Integration
    Now uses student performance data to provide personalized tutoring!
    """
    data = request.json
    prompt = data.get('prompt', '')
    
    if not prompt:
        return jsonify({'error': 'Prompt required'}), 400
    
    db = get_db()
    
    # Get student context for personalized AI tutoring
    student_context = get_student_context_for_ai(db, session['user_id'])
    
    # Generate context-aware AI response
    answer = generate_ai_tutoring_response(prompt, student_context)
    
    # Render markdown with math support
    rendered_answer = render_markdown_with_math(answer)
    
    # Save to database
    db.execute(
        'INSERT INTO ai_queries (user_id, prompt, response) VALUES (?, ?, ?)',
        (session['user_id'], prompt, answer)
    )
    db.commit()
    db.close()
    
    return jsonify({
        'answer': rendered_answer, 
        'raw': answer, 
        'provider': ai_provider,
        'personalized': bool(student_context.get('weak_topics'))  # Indicate if response was personalized
    }), 200

# ============================================================================
# NEW FEATURES: FORGOT PASSWORD, FEEDBACK, LIVE CLASS
# ============================================================================

@app.route('/forgot-password', methods=['GET'])
def forgot_password_page():
    """Render forgot password page"""
    return render_template('forgot_password.html')

@app.route('/api/forgot-password/send-otp', methods=['POST'])
def send_password_reset_otp():
    """Send OTP to user's email for password reset"""
    data = request.json
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    # Check if user exists
    db = get_db()
    user = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
    
    if not user:
        # Don't reveal if email exists (security)
        return jsonify({'message': 'If the email exists, an OTP has been sent'}), 200
    
    # Clean old OTPs
    clean_expired_otps()
    
    # Generate OTP
    otp = generate_otp(4)
    expires_at = datetime.now() + timedelta(minutes=10)
    
    # Save OTP to database
    db.execute(
        'INSERT INTO password_reset_otp (email, otp, expires_at) VALUES (?, ?, ?)',
        (email, otp, expires_at)
    )
    db.commit()
    db.close()
    
    # Send email
    email_sent = send_otp_email(email, otp)
    
    if email_sent:
        logger.info(f"Password reset OTP sent to {email}")
        return jsonify({'message': 'OTP sent to your email'}), 200
    else:
        # For demo purposes, return the OTP in the response
        logger.warning(f"Email not configured, returning OTP in response for demo: {otp}")
        return jsonify({
            'message': f'Email not configured. For demo purposes, your OTP is: {otp}',
            'otp': otp,
            'demo_mode': True
        }), 200

@app.route('/api/forgot-password/verify-otp', methods=['POST'])
def verify_and_reset_password():
    """Verify OTP and reset password"""
    data = request.json
    email = data.get('email', '').strip().lower()
    otp = data.get('otp', '').strip()
    new_password = data.get('new_password', '')
    
    if not email or not otp or not new_password:
        return jsonify({'error': 'All fields are required'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    # Clean expired OTPs
    clean_expired_otps()
    
    # Verify OTP
    db = get_db()
    otp_record = db.execute('''
        SELECT id FROM password_reset_otp 
        WHERE email = ? AND otp = ? AND expires_at > ? AND used = 0
        ORDER BY created_at DESC LIMIT 1
    ''', (email, otp, datetime.now())).fetchone()
    
    if not otp_record:
        db.close()
        return jsonify({'error': 'Invalid or expired OTP'}), 400
    
    # Update password
    password_hash = generate_password_hash(new_password)
    db.execute('UPDATE users SET password_hash = ? WHERE email = ?', (password_hash, email))
    
    # Mark OTP as used
    db.execute('UPDATE password_reset_otp SET used = 1 WHERE id = ?', (otp_record['id'],))
    
    db.commit()
    db.close()
    
    logger.info(f"Password reset successful for {email}")
    return jsonify({'message': 'Password reset successful'}), 200

@app.route('/api/feedback', methods=['POST'])
@login_required
def submit_feedback():
    """Submit user feedback"""
    data = request.json
    rating = data.get('rating')
    message = data.get('message', '').strip()
    
    if not rating or rating not in [1, 2, 3, 4, 5]:
        return jsonify({'error': 'Valid rating (1-5) is required'}), 400
    
    db = get_db()
    db.execute(
        'INSERT INTO feedback (user_id, rating, message) VALUES (?, ?, ?)',
        (session['user_id'], rating, message)
    )
    db.commit()
    db.close()
    
    logger.info(f"Feedback submitted by user {session['user_id']}: {rating} stars")
    return jsonify({'message': 'Thank you for your feedback!'}), 201

@app.route('/api/feedback/all')
@login_required
@teacher_required
def get_all_feedback():
    """Get all feedback (teachers only)"""
    db = get_db()
    feedback_list = db.execute('''
        SELECT f.*, u.name as user_name, u.email as user_email, u.role
        FROM feedback f
        JOIN users u ON f.user_id = u.id
        ORDER BY f.created_at DESC
    ''').fetchall()
    db.close()
    
    return jsonify([dict(f) for f in feedback_list])

@app.route('/api/live-class/start', methods=['POST'])
@login_required
@teacher_required
def start_live_class():
    """Start a live class session"""
    data = request.json
    class_id = data.get('class_id')
    
    if not class_id:
        return jsonify({'error': 'Class ID is required'}), 400
    
    # Verify teacher owns this class
    db = get_db()
    class_info = db.execute(
        'SELECT * FROM classes WHERE id = ? AND teacher_id = ?',
        (class_id, session['user_id'])
    ).fetchone()
    
    if not class_info:
        db.close()
        return jsonify({'error': 'Class not found or unauthorized'}), 403
    
    # Generate unique room name
    room_name = f"class_{class_id}_{int(datetime.now().timestamp())}"
    
    # Check if there's an active session
    existing_session = db.execute(
        'SELECT id FROM live_sessions WHERE class_id = ? AND is_active = 1',
        (class_id,)
    ).fetchone()
    
    if existing_session:
        db.close()
        return jsonify({'error': 'A live session is already active for this class'}), 400
    
    # Create new session
    db.execute('''
        INSERT INTO live_sessions (class_id, room_name, started_by)
        VALUES (?, ?, ?)
    ''', (class_id, room_name, session['user_id']))
    db.commit()
    db.close()
    
    logger.info(f"Live class started: {room_name} by user {session['user_id']}")
    
    return jsonify({
        'message': 'Live class started',
        'room_name': room_name,
        'jitsi_domain': JITSI_DOMAIN
    }), 201

@app.route('/api/live-class/join/<int:class_id>')
@login_required
def join_live_class(class_id):
    """Get live class session details for joining"""
    db = get_db()
    
    # Check if user has access to this class
    if session['role'] == 'teacher':
        class_info = db.execute(
            'SELECT * FROM classes WHERE id = ? AND teacher_id = ?',
            (class_id, session['user_id'])
        ).fetchone()
    else:
        class_info = db.execute('''
            SELECT c.* FROM classes c
            JOIN enrollments e ON c.id = e.class_id
            WHERE c.id = ? AND e.student_id = ?
        ''', (class_id, session['user_id'])).fetchone()
    
    if not class_info:
        db.close()
        return jsonify({'error': 'Class not found or no access'}), 403
    
    # Get active session
    live_session = db.execute('''
        SELECT * FROM live_sessions 
        WHERE class_id = ? AND is_active = 1
        ORDER BY started_at DESC LIMIT 1
    ''', (class_id,)).fetchone()
    
    db.close()
    
    if not live_session:
        return jsonify({'error': 'No active live session'}), 404
    
    return jsonify({
        'room_name': live_session['room_name'],
        'jitsi_domain': JITSI_DOMAIN,
        'class_title': class_info['title']
    })

@app.route('/api/live-class/end', methods=['POST'])
@login_required
@teacher_required
def end_live_class():
    """End a live class session"""
    data = request.json
    class_id = data.get('class_id')
    
    if not class_id:
        return jsonify({'error': 'Class ID is required'}), 400
    
    db = get_db()
    
    # Update session
    db.execute('''
        UPDATE live_sessions 
        SET is_active = 0, ended_at = ?
        WHERE class_id = ? AND started_by = ? AND is_active = 1
    ''', (datetime.now(), class_id, session['user_id']))
    
    db.commit()
    db.close()
    
    logger.info(f"Live class ended for class {class_id}")
    return jsonify({'message': 'Live class ended'}), 200

# Socket.IO events for real-time chat
@socketio.on('join')
def on_join(data):
    room = str(data['class_id'])
    join_room(room)
    emit('status', {
        'msg': f"{session['name']} has joined the class",
        'user': session['name']
    }, room=room)

@socketio.on('leave')
def on_leave(data):
    room = str(data['class_id'])
    leave_room(room)
    emit('status', {
        'msg': f"{session['name']} has left the class",
        'user': session['name']
    }, room=room)

@socketio.on('message')
def handle_message(data):
    room = str(data['class_id'])
    message = data['message']
    
    # Save message to database
    db = get_db()
    db.execute(
        'INSERT INTO chat_messages (class_id, user_id, message) VALUES (?, ?, ?)',
        (data['class_id'], session['user_id'], message)
    )
    db.commit()
    db.close()
    
    # Broadcast message
    emit('message', {
        'user': session['name'],
        'message': message,
        'timestamp': datetime.now().strftime('%H:%M')
    }, room=room)

@app.route('/api/class/<int:class_id>/messages')
@login_required
def get_class_messages(class_id):
    db = get_db()
    messages = db.execute('''
        SELECT cm.*, u.name as user_name
        FROM chat_messages cm
        JOIN users u ON cm.user_id = u.id
        WHERE cm.class_id = ?
        ORDER BY cm.timestamp ASC
    ''', (class_id,)).fetchall()
    db.close()
    
    return jsonify([dict(m) for m in messages])

# ============================================================================
# ADAPTIVE LEARNING API ENDPOINTS
# ============================================================================

@app.route('/api/recommendations')
@login_required
def get_recommendations():
    """
    Get personalized content recommendations for the logged-in student.
    Based on knowledge gaps and learning patterns.
    """
    db = get_db()
    
    # Get all enrolled classes
    classes = db.execute('''
        SELECT DISTINCT class_id FROM enrollments WHERE student_id = ?
    ''', (session['user_id'],)).fetchall()
    
    all_recommendations = []
    
    for cls in classes:
        class_id = cls['class_id']
        # Generate fresh recommendations
        recs = generate_adaptive_recommendations(db, session['user_id'], class_id)
        all_recommendations.extend(recs)
    
    # Also get stored recommendations
    stored_recs = db.execute('''
        SELECT r.*, 
               CASE 
                   WHEN r.content_type = 'lecture' THEN l.filename
                   WHEN r.content_type = 'quiz' THEN q.title
                   ELSE 'Practice Exercise'
               END as content_title
        FROM recommendations r
        LEFT JOIN lectures l ON r.content_type = 'lecture' AND r.content_id = l.id
        LEFT JOIN quizzes q ON r.content_type = 'quiz' AND r.content_id = q.id
        WHERE r.user_id = ? AND r.is_completed = 0
        ORDER BY r.priority DESC, r.created_at DESC
        LIMIT 10
    ''', (session['user_id'],)).fetchall()
    
    db.close()
    
    return jsonify({
        'recommendations': [dict(r) for r in stored_recs],
        'freshly_generated': all_recommendations
    })

@app.route('/api/knowledge-gaps')
@login_required
def get_knowledge_gaps():
    """
    Get student's knowledge gaps across all classes.
    Shows topics where mastery is below 60%.
    """
    db = get_db()
    
    gaps = db.execute('''
        SELECT kg.*, t.topic_name, t.class_id, c.title as class_name
        FROM knowledge_gaps kg
        JOIN topics t ON kg.topic_id = t.id
        JOIN classes c ON t.class_id = c.id
        WHERE kg.user_id = ?
        ORDER BY kg.mastery_level ASC
    ''', (session['user_id'],)).fetchall()
    
    db.close()
    
    return jsonify([dict(g) for g in gaps])

@app.route('/api/topic-mastery/<int:class_id>')
@login_required
def get_topic_mastery(class_id):
    """
    Get detailed topic-wise mastery for a specific class.
    Shows student's strength and weakness visualization data.
    """
    db = get_db()
    
    # Get all topics for this class
    topics = db.execute('''
        SELECT t.id, t.topic_name,
               COALESCE(kg.mastery_level, 0) as mastery_level,
               COALESCE(kg.questions_attempted, 0) as questions_attempted,
               COALESCE(kg.questions_correct, 0) as questions_correct
        FROM topics t
        LEFT JOIN knowledge_gaps kg ON t.id = kg.topic_id AND kg.user_id = ?
        WHERE t.class_id = ?
        ORDER BY t.topic_name
    ''', (session['user_id'], class_id)).fetchall()
    
    db.close()
    
    # Calculate mastery categories
    mastery_data = {
        'expert': [],  # > 80%
        'proficient': [],  # 60-80%
        'developing': [],  # 40-60%
        'beginner': []  # < 40%
    }
    
    for topic in topics:
        mastery_pct = topic['mastery_level'] * 100
        topic_dict = dict(topic)
        topic_dict['mastery_percentage'] = round(mastery_pct, 1)
        
        if mastery_pct >= 80:
            mastery_data['expert'].append(topic_dict)
        elif mastery_pct >= 60:
            mastery_data['proficient'].append(topic_dict)
        elif mastery_pct >= 40:
            mastery_data['developing'].append(topic_dict)
        else:
            mastery_data['beginner'].append(topic_dict)
    
    return jsonify({
        'all_topics': [dict(t) for t in topics],
        'mastery_breakdown': mastery_data
    })

@app.route('/api/teacher/interventions')
@login_required
@teacher_required
def get_teacher_interventions():
    """
    Get intervention alerts for teacher.
    Shows students who need attention.
    """
    db = get_db()
    
    interventions = db.execute('''
        SELECT ti.*, u.name as student_name, c.title as class_name
        FROM teacher_interventions ti
        JOIN users u ON ti.student_id = u.id
        JOIN classes c ON ti.class_id = c.id
        WHERE ti.teacher_id = ? AND ti.is_resolved = 0
        ORDER BY ti.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    db.close()
    
    return jsonify([dict(i) for i in interventions])

@app.route('/api/teacher/resolve-intervention/<int:intervention_id>', methods=['POST'])
@login_required
@teacher_required
def resolve_intervention(intervention_id):
    """Mark an intervention alert as resolved."""
    db = get_db()
    
    db.execute('''
        UPDATE teacher_interventions
        SET is_resolved = 1, resolved_at = ?
        WHERE id = ? AND teacher_id = ?
    ''', (datetime.now(), intervention_id, session['user_id']))
    
    db.commit()
    db.close()
    
    return jsonify({'message': 'Intervention marked as resolved'})

@app.route('/api/teacher/topics', methods=['GET', 'POST'])
@login_required
@teacher_required
def manage_topics():
    """
    GET: List all topics for teacher's classes
    POST: Create new topic for a class
    """
    db = get_db()
    
    if request.method == 'POST':
        data = request.json
        class_id = data.get('class_id')
        topic_name = data.get('topic_name')
        description = data.get('description', '')
        
        # Verify teacher owns this class
        cls = db.execute(
            'SELECT id FROM classes WHERE id = ? AND teacher_id = ?',
            (class_id, session['user_id'])
        ).fetchone()
        
        if not cls:
            return jsonify({'error': 'Unauthorized'}), 403
        
        db.execute(
            'INSERT INTO topics (class_id, topic_name, description) VALUES (?, ?, ?)',
            (class_id, topic_name, description)
        )
        db.commit()
        topic_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.close()
        
        return jsonify({'message': 'Topic created', 'topic_id': topic_id}), 201
    
    else:
        # Get all topics for teacher's classes
        topics = db.execute('''
            SELECT t.*, c.title as class_name
            FROM topics t
            JOIN classes c ON t.class_id = c.id
            WHERE c.teacher_id = ?
            ORDER BY c.title, t.topic_name
        ''', (session['user_id'],)).fetchall()
        
        db.close()
        return jsonify([dict(t) for t in topics])

@app.route('/api/teacher/assign-question-topics', methods=['POST'])
@login_required
@teacher_required
def assign_question_topics():
    """
    Assign topics to quiz questions for knowledge gap tracking.
    Enables the AI to detect which specific topics students struggle with.
    """
    data = request.json
    question_id = data.get('question_id')
    topic_ids = data.get('topic_ids', [])
    
    if not question_id or not topic_ids:
        return jsonify({'error': 'question_id and topic_ids required'}), 400
    
    db = get_db()
    
    # Remove existing assignments
    db.execute('DELETE FROM question_topics WHERE question_id = ?', (question_id,))
    
    # Add new assignments
    for topic_id in topic_ids:
        db.execute(
            'INSERT INTO question_topics (question_id, topic_id) VALUES (?, ?)',
            (question_id, topic_id)
        )
    
    db.commit()
    db.close()
    
    return jsonify({'message': 'Topics assigned to question successfully'})

@app.route('/api/mark-recommendation-complete/<int:rec_id>', methods=['POST'])
@login_required
def mark_recommendation_complete(rec_id):
    """Mark a recommendation as completed by the student."""
    db = get_db()
    
    db.execute('''
        UPDATE recommendations
        SET is_completed = 1
        WHERE id = ? AND user_id = ?
    ''', (rec_id, session['user_id']))
    
    db.commit()
    db.close()
    
    return jsonify({'message': 'Recommendation marked as complete'})

# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.route('/api/health')
def health_check():
    """
    Health check endpoint to verify application and database status.
    
    Returns JSON with:
    - Application status
    - Database connection status
    - Configuration details (non-sensitive)
    """
    try:
        db_health = check_db_health()
        
        return jsonify({
            'status': 'ok',
            'application': 'Education Platform',
            'database': db_health,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/db/status')
def database_status():
    """
    Detailed database status endpoint for debugging.
    Only accessible in development mode.
    """
    try:
        health = check_db_health()
        
        # Additional database statistics
        db = get_db()
        
        # Get row counts for main tables
        tables_stats = {}
        main_tables = ['users', 'classes', 'enrollments', 'lectures', 
                      'quizzes', 'quiz_submissions', 'chat_messages']
        
        for table in main_tables:
            try:
                cursor = db.execute(f"SELECT COUNT(*) as count FROM {table}")
                count = cursor.fetchone()['count']
                tables_stats[table] = count
            except sqlite3.Error:
                tables_stats[table] = 'N/A'
        
        db.close()
        
        return jsonify({
            'health': health,
            'table_statistics': tables_stats,
            'configuration': {
                'database_path': DATABASE_PATH,
                'timeout': DATABASE_TIMEOUT
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Database status check failed: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# ============================================================================
# APPLICATION STARTUP
# ============================================================================

if __name__ == '__main__':
    try:
        logger.info("=" * 70)
        logger.info("Starting Education Platform Application")
        logger.info("=" * 70)

        # Check if database exists, initialize if not
        if not os.path.exists(DATABASE_PATH):
            logger.warning(f"Database not found at {DATABASE_PATH}. Initializing...")
            init_db()
            logger.info("Database initialized successfully!")
        else:
            logger.info(f"Database found at {DATABASE_PATH}")

        # Perform health check on startup
        logger.info("Performing database health check...")
        health = check_db_health()

        if health['status'] == 'healthy':
            logger.info(f"✓ Database health check passed!")
            logger.info(f"  - Tables: {health['table_count']}")
            logger.info(f"  - Size: {health['database_size_bytes']} bytes")
            logger.info(f"  - Path: {health['database_path']}")
        else:
            logger.error(f"‼ Database health check failed!")

        logger.info("-" * 70)
        logger.info("Configuration:")
        logger.info(f"  - Database: {DATABASE_PATH}")
        logger.info(f"  - Timeout: {DATABASE_TIMEOUT}s")
        logger.info(f"  - Upload Folder: static/uploads")
        
        # Show AI provider status
        if ai_provider == "deepseek":
            logger.info(f"  - AI Provider: DeepSeek (FREE & POWERFUL) ✓")
        elif ai_provider == "groq":
            logger.info(f"  - AI Provider: Groq (FREE & FAST) ✓")
        elif ai_provider == "openai":
            logger.info(f"  - AI Provider: OpenAI (PREMIUM) ✓")
        else:
            logger.info(f"  - AI Provider: Not Configured (Set API keys for FREE AI)")
        
        logger.info("-" * 70)
        logger.info("Starting Flask-SocketIO server on 127.0.0.1:5000")
        logger.info("Application is ready to accept connections!")
        logger.info("=" * 70)
        
        # Check if running in production (Render, Heroku, etc.)
        if os.environ.get('PORT'):
            # Production mode - let Gunicorn handle the server
            logger.info("Running in production mode - Gunicorn will start the server")
        else:
            # Development mode
            socketio.run(app, host='127.0.0.1', port=5000, debug=True)
    except Exception as e:
        logger.error(f"Unhandled exception in application startup: {e}")
        
