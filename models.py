"""
SQLAlchemy ORM models for LearnVaultX.
Used by Flask-Migrate for schema management.
These models define the PostgreSQL schema; actual queries still use raw SQL
through the DatabaseManager compatibility layer.
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


# ─── CORE ──────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(320), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'student' or 'teacher'
    is_verified = db.Column(db.Integer, default=0)
    verified_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Class(db.Model):
    __tablename__ = 'classes'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    code = db.Column(db.String(10), unique=True)
    subject = db.Column(db.String(200), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False, index=True)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('student_id', 'class_id'),)


class Lecture(db.Model):
    __tablename__ = 'lectures'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False, index=True)
    filename = db.Column(db.Text, nullable=False)
    filepath = db.Column(db.Text, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


# ─── QUIZZES ───────────────────────────────────────────────────

class Quiz(db.Model):
    __tablename__ = 'quizzes'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    difficulty_level = db.Column(db.String(50))
    generated_by = db.Column(db.Integer)
    module_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class QuizQuestion(db.Model):
    __tablename__ = 'quiz_questions'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False, index=True)
    question_text = db.Column(db.Text, nullable=False)
    options = db.Column(db.Text, nullable=False)  # JSON array
    correct_option_index = db.Column(db.Integer, nullable=False)
    topic_tag = db.Column(db.String(200), default='')
    difficulty = db.Column(db.String(50), default='')


class QuizSubmission(db.Model):
    __tablename__ = 'quiz_submissions'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    score = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    answers = db.Column(db.Text, nullable=False, default='{}')  # JSON
    duration_seconds = db.Column(db.Integer)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─── AI ────────────────────────────────────────────────────────

class AIQuery(db.Model):
    __tablename__ = 'ai_queries'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    prompt = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    provider = db.Column(db.String(50), default='Groq')
    mode = db.Column(db.String(50), default='expert')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AIContextSession(db.Model):
    __tablename__ = 'ai_context_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    session_data = db.Column(db.Text, nullable=False)  # JSON
    weak_topics = db.Column(db.Text)  # JSON
    recent_performance = db.Column(db.Text)  # JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)


class AITutorSession(db.Model):
    __tablename__ = 'ai_tutor_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    message = db.Column(db.Text)
    response = db.Column(db.Text)
    emotion = db.Column(db.String(50))
    gesture = db.Column(db.String(50))
    recommended_actions = db.Column(db.Text)  # JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatMemory(db.Model):
    __tablename__ = 'chat_memory'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    message = db.Column(db.Text)
    role = db.Column(db.String(20))  # 'user' or 'assistant'
    topic_tag = db.Column(db.String(100), default='')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


# ─── ANALYTICS ─────────────────────────────────────────────────

class StudentMetrics(db.Model):
    __tablename__ = 'student_metrics'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), primary_key=True)
    score_avg = db.Column(db.Float, default=0)
    avg_time = db.Column(db.Float, default=0)
    pace_score = db.Column(db.Float, default=0)
    rating = db.Column(db.Float, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class TopicModel(db.Model):
    __tablename__ = 'topics'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False, index=True)
    topic_name = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class QuestionTopic(db.Model):
    __tablename__ = 'question_topics'
    question_id = db.Column(db.Integer, db.ForeignKey('quiz_questions.id'), primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), primary_key=True)


class KnowledgeGap(db.Model):
    __tablename__ = 'knowledge_gaps'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    mastery_level = db.Column(db.Float, default=0.0)
    questions_attempted = db.Column(db.Integer, default=0)
    questions_correct = db.Column(db.Integer, default=0)
    last_assessed = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'topic_id'),)


class TopicMastery(db.Model):
    __tablename__ = 'topic_mastery'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    mastery_score = db.Column(db.Float, default=0.0)
    confidence_level = db.Column(db.String(30), default='beginner')
    time_spent = db.Column(db.Integer, default=0)
    last_practiced = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'topic_id'),)


class Recommendation(db.Model):
    __tablename__ = 'recommendations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    content_type = db.Column(db.String(50), nullable=False)
    content_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(300), default='')
    description = db.Column(db.Text, default='')
    action = db.Column(db.String(100), default='View')
    reason = db.Column(db.Text, nullable=False)
    priority = db.Column(db.Integer, default=0)
    is_completed = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class LearningPath(db.Model):
    __tablename__ = 'learning_paths'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    path_data = db.Column(db.Text, nullable=False)  # JSON
    progress = db.Column(db.Float, default=0.0)
    created_by_ai = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)


# ─── MODULES ──────────────────────────────────────────────────

class LearningModule(db.Model):
    __tablename__ = 'learning_modules'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, default='')
    order_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StudentModuleProgress(db.Model):
    __tablename__ = 'student_module_progress'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    module_id = db.Column(db.Integer, db.ForeignKey('learning_modules.id'), nullable=False)
    status = db.Column(db.String(30), default='NOT_STARTED')
    completion_percent = db.Column(db.Float, default=0)
    quiz_score_avg = db.Column(db.Float, default=0)
    completed_at = db.Column(db.DateTime)
    __table_args__ = (db.UniqueConstraint('user_id', 'module_id'),)


# ─── SKILL TREE ─────────────────────────────────────────────

class SkillTreeNode(db.Model):
    __tablename__ = 'skill_tree_nodes'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, default='')
    icon = db.Column(db.String(10), default='📘')
    position_order = db.Column(db.Integer, default=0)
    prerequisite_node_id = db.Column(db.Integer, db.ForeignKey('skill_tree_nodes.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StudentSkillProgress(db.Model):
    __tablename__ = 'student_skill_progress'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    node_id = db.Column(db.Integer, db.ForeignKey('skill_tree_nodes.id'), nullable=False)
    status = db.Column(db.String(30), default='locked')
    score = db.Column(db.Float, default=0)
    unlocked_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    __table_args__ = (db.UniqueConstraint('student_id', 'node_id'),)


class SkillTreeProgress(db.Model):
    __tablename__ = 'skill_tree_progress'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    node_id = db.Column(db.Integer, db.ForeignKey('skill_tree_nodes.id'), nullable=False)
    status = db.Column(db.String(30), default='locked')
    score = db.Column(db.Float, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('student_id', 'node_id'),)


# ─── GAMIFICATION ─────────────────────────────────────────────

class UserBadge(db.Model):
    __tablename__ = 'user_badges'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    badge_code = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    icon = db.Column(db.String(10), default='🏆')
    awarded_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'badge_code'),)


class StudentAdaptiveProfile(db.Model):
    __tablename__ = 'student_adaptive_profile'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    current_level = db.Column(db.String(30), default='medium')
    weak_topics_json = db.Column(db.Text, default='[]')
    last_score = db.Column(db.Float, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('student_id', 'class_id'),)


class MistakeNote(db.Model):
    __tablename__ = 'mistake_notes'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    question_id = db.Column(db.Integer)
    topic_tag = db.Column(db.String(200), default='')
    mistake_summary = db.Column(db.Text, default='')
    quick_fix = db.Column(db.Text, default='')
    memory_trick = db.Column(db.Text, default='')
    recommended_topic = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─── MICRO LEARNING ───────────────────────────────────────────

class MicroTask(db.Model):
    __tablename__ = 'micro_tasks'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    task_date = db.Column(db.String(20), nullable=False)
    topic_tag = db.Column(db.String(200))
    status = db.Column(db.String(30), default='PENDING')
    progress = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MLFlashcard(db.Model):
    __tablename__ = 'ml_flashcards'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('micro_tasks.id'), nullable=False, index=True)
    front = db.Column(db.Text, nullable=False)
    back = db.Column(db.Text, nullable=False)
    topic = db.Column(db.String(200))
    is_completed = db.Column(db.Integer, default=0)


class MLCoding(db.Model):
    __tablename__ = 'ml_coding'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('micro_tasks.id'), nullable=False, index=True)
    prompt = db.Column(db.Text, nullable=False)
    starter_code = db.Column(db.Text)
    solution_code = db.Column(db.Text)
    topic = db.Column(db.String(200))
    test_case = db.Column(db.Text)
    is_completed = db.Column(db.Integer, default=0)


class MLQuizBooster(db.Model):
    __tablename__ = 'ml_quiz_booster'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('micro_tasks.id'), nullable=False, index=True)
    question = db.Column(db.Text, nullable=False)
    options = db.Column(db.Text)
    correct_answer = db.Column(db.Text)
    topic = db.Column(db.String(200))
    is_completed = db.Column(db.Integer, default=0)


# ─── OTP / AUTH ────────────────────────────────────────────────

class PasswordResetOTP(db.Model):
    __tablename__ = 'password_reset_otp'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(320), nullable=False, index=True)
    otp = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Integer, default=0)
    attempts = db.Column(db.Integer, default=0)


class OTPRequest(db.Model):
    __tablename__ = 'otp_requests'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(320), nullable=False, index=True)
    otp_hash = db.Column(db.Text, nullable=False)
    otp_type = db.Column(db.String(30), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, default=0)
    is_used = db.Column(db.Integer, default=0)


# ─── LIVE SESSIONS ─────────────────────────────────────────────

class LiveSession(db.Model):
    __tablename__ = 'live_sessions'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False, index=True)
    room_name = db.Column(db.String(200), nullable=False, unique=True)
    started_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_active = db.Column(db.Integer, default=1)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)


# ─── FEEDBACK / INTERVENTIONS ─────────────────────────────────

class Feedback(db.Model):
    __tablename__ = 'feedback'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TeacherIntervention(db.Model):
    __tablename__ = 'teacher_interventions'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    alert_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_resolved = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)


# ─── EXAM ARENA ───────────────────────────────────────────────

class ArenaProfile(db.Model):
    __tablename__ = 'arena_profiles'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    exam = db.Column(db.String(50), nullable=False, default='JEE')
    subject = db.Column(db.String(100), nullable=False, default='Physics')
    mode = db.Column(db.String(50), nullable=False, default='Practice')
    preferred_difficulty = db.Column(db.String(30), nullable=False, default='Auto')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class ArenaQuestionBank(db.Model):
    __tablename__ = 'arena_question_bank'
    id = db.Column(db.Integer, primary_key=True)
    exam = db.Column(db.String(50), nullable=False, index=True)
    subject = db.Column(db.String(100), nullable=False, index=True)
    topic_tag = db.Column(db.String(200), nullable=False, default='')
    difficulty = db.Column(db.String(30), nullable=False, default='Medium')
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.Text, nullable=False)
    option_b = db.Column(db.Text, nullable=False)
    option_c = db.Column(db.Text, nullable=False)
    option_d = db.Column(db.Text, nullable=False)
    correct_option = db.Column(db.String(5), nullable=False)
    explanation = db.Column(db.Text, nullable=False, default='')
    estimated_time_seconds = db.Column(db.Integer, nullable=False, default=60)
    source_tag = db.Column(db.String(50), nullable=False, default='AI_GENERATED')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ArenaAttempt(db.Model):
    __tablename__ = 'arena_attempts'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    exam = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    attempt_type = db.Column(db.String(30), nullable=False, default='mock')
    difficulty_start = db.Column(db.String(30), default='Medium')
    difficulty_end = db.Column(db.String(30), default='Medium')
    score = db.Column(db.Integer, nullable=False, default=0)
    total_questions = db.Column(db.Integer, nullable=False, default=0)
    accuracy_percent = db.Column(db.Float, nullable=False, default=0)
    avg_time_per_question = db.Column(db.Float, nullable=False, default=0)
    time_taken_total = db.Column(db.Integer, nullable=False, default=0)
    xp_earned = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(30), default='ongoing')
    questions_json = db.Column(db.Text, default='[]')
    current_q_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class ArenaAttemptAnswer(db.Model):
    __tablename__ = 'arena_attempt_answers'
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('arena_attempts.id'), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey('arena_question_bank.id'), nullable=False)
    selected_option = db.Column(db.String(5))
    is_correct = db.Column(db.Integer, nullable=False, default=0)
    time_taken_seconds = db.Column(db.Float, nullable=False, default=0)
    # Snapshot columns
    question_text = db.Column(db.Text, default='')
    option_a = db.Column(db.Text, default='')
    option_b = db.Column(db.Text, default='')
    option_c = db.Column(db.Text, default='')
    option_d = db.Column(db.Text, default='')
    correct_option = db.Column(db.Text, default='')
    explanation = db.Column(db.Text, default='')


class ArenaTopicMastery(db.Model):
    __tablename__ = 'arena_topic_mastery'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    exam = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    topic_tag = db.Column(db.String(200), nullable=False)
    mastery_score = db.Column(db.Float, nullable=False, default=0)
    weak_flag = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('student_id', 'exam', 'subject', 'topic_tag'),)


class ArenaRankStatus(db.Model):
    __tablename__ = 'arena_rank_status'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    rank_name = db.Column(db.String(30), nullable=False, default='Bronze')
    xp_total = db.Column(db.Integer, nullable=False, default=0)
    streak_days = db.Column(db.Integer, nullable=False, default=0)
    last_daily_date = db.Column(db.String(20), default='')
    readiness_score = db.Column(db.Float, nullable=False, default=0)
    level = db.Column(db.Integer, default=1)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class ArenaAINote(db.Model):
    __tablename__ = 'arena_ai_notes'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('arena_attempts.id'), nullable=False)
    topic_tag = db.Column(db.String(200), nullable=False, default='')
    mistake_summary = db.Column(db.Text, nullable=False, default='')
    quick_fix = db.Column(db.Text, nullable=False, default='')
    memory_trick = db.Column(db.Text, nullable=False, default='')
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)


class ArenaXPLog(db.Model):
    __tablename__ = 'arena_xp_log'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    source = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ArenaAchievement(db.Model):
    __tablename__ = 'arena_achievements'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    achievement_code = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    icon = db.Column(db.String(10), default='🏆')
    unlocked_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('student_id', 'achievement_code'),)


class ArenaMission(db.Model):
    __tablename__ = 'arena_missions'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    mission_id = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(30), default='locked')
    stars = db.Column(db.Integer, default=0)
    score = db.Column(db.Integer, default=0)
    completed_at = db.Column(db.DateTime)
    __table_args__ = (db.UniqueConstraint('student_id', 'mission_id'),)


class ArenaRevisionPlan(db.Model):
    __tablename__ = 'arena_revision_plans'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('arena_attempts.id'), nullable=False)
    exam = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    mistake_summary = db.Column(db.Text, default='')
    revision_notes = db.Column(db.Text, default='')
    practice_questions = db.Column(db.Text, default='[]')  # JSON
    topic_suggestions = db.Column(db.Text, default='[]')  # JSON
    readiness_before = db.Column(db.Float, default=0)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
