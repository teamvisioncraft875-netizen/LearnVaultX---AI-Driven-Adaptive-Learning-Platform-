"""
Database schema migration — ensures all required tables and columns exist.
Run on every startup so the DB stays in sync with the application code.
"""
import sqlite3
import logging

logger = logging.getLogger(__name__)


def _add_column_if_missing(conn, table, column, col_type, default=None):
    """Add a column to a table if it doesn't already exist."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    existing = [row[1] for row in cursor.fetchall()]
    if column not in existing:
        default_clause = f" DEFAULT {default}" if default is not None else ""
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}")
        logger.info(f"Added column {table}.{column}")


def _auto_generate_learning_modules(conn):
    """Auto-generate learning modules for classes that have none."""
    cursor = conn.execute("SELECT id, title FROM classes")
    classes = cursor.fetchall()

    for cls_id, cls_title in classes:
        existing = conn.execute(
            "SELECT COUNT(*) FROM learning_modules WHERE class_id = ?", (cls_id,)
        ).fetchone()[0]

        if existing > 0:
            continue

        modules = [
            (cls_id, f"Introduction to {cls_title}", f"Foundation concepts and overview of {cls_title}", 1),
            (cls_id, "Core Concepts", f"Essential building blocks of {cls_title}", 2),
            (cls_id, "Practical Applications", f"Hands-on exercises in {cls_title}", 3),
            (cls_id, "Intermediate Topics", f"Deeper exploration of {cls_title}", 4),
            (cls_id, "Advanced Concepts", f"Complex topics in {cls_title}", 5),
            (cls_id, "Problem Solving", "Real-world problems and solutions", 6),
            (cls_id, "Review & Assessment", "Comprehensive review and final assessment", 7),
        ]

        for m in modules:
            conn.execute(
                "INSERT INTO learning_modules (class_id, title, description, order_index) VALUES (?, ?, ?, ?)",
                m
            )
        logger.info(f"Auto-generated 7 learning modules for class {cls_id} ({cls_title})")


def ensure_schema(db_path):
    """Create missing tables and add missing columns to bring DB up to date."""
    conn = sqlite3.connect(db_path)
    try:
        # ── Create all missing tables ───────────────────────────────────

        conn.executescript("""
            -- Skill tree nodes per class
            CREATE TABLE IF NOT EXISTS skill_tree_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                icon TEXT DEFAULT '📘',
                position_order INTEGER DEFAULT 0,
                prerequisite_node_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (class_id) REFERENCES classes(id),
                FOREIGN KEY (prerequisite_node_id) REFERENCES skill_tree_nodes(id)
            );

            -- Per-student progress on skill tree nodes
            -- NOTE: skill_tree_engine.py uses THIS table name
            CREATE TABLE IF NOT EXISTS student_skill_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                node_id INTEGER NOT NULL,
                status TEXT DEFAULT 'locked',
                score REAL DEFAULT 0,
                unlocked_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (node_id) REFERENCES skill_tree_nodes(id),
                UNIQUE(student_id, node_id)
            );

            -- Also keep the old name as an alias (some routes might reference it)
            CREATE TABLE IF NOT EXISTS skill_tree_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                node_id INTEGER NOT NULL,
                status TEXT DEFAULT 'locked',
                score REAL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (node_id) REFERENCES skill_tree_nodes(id),
                UNIQUE(student_id, node_id)
            );

            -- Learning modules per class  
            CREATE TABLE IF NOT EXISTS learning_modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                order_index INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (class_id) REFERENCES classes(id)
            );

            -- Per-student module progress
            CREATE TABLE IF NOT EXISTS student_module_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                module_id INTEGER NOT NULL,
                status TEXT DEFAULT 'NOT_STARTED',
                completion_percent REAL DEFAULT 0,
                quiz_score_avg REAL DEFAULT 0,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (module_id) REFERENCES learning_modules(id),
                UNIQUE(user_id, module_id)
            );

            -- User badges (badges.py)
            CREATE TABLE IF NOT EXISTS user_badges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                badge_code TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                icon TEXT DEFAULT '🏆',
                awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, badge_code)
            );

            -- Adaptive quiz profile per student per class (adaptive_quiz_generator.py)
            CREATE TABLE IF NOT EXISTS student_adaptive_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                current_level TEXT DEFAULT 'medium',
                weak_topics_json TEXT DEFAULT '[]',
                last_score REAL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (class_id) REFERENCES classes(id),
                UNIQUE(student_id, class_id)
            );

            -- Mistake notes from quiz submissions (adaptive_quiz_generator.py)
            CREATE TABLE IF NOT EXISTS micro_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                task_date TEXT NOT NULL,
                topic_tag TEXT,
                status TEXT DEFAULT 'PENDING',
                progress REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (class_id) REFERENCES classes(id)
            );

            CREATE TABLE IF NOT EXISTS ml_flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                front TEXT NOT NULL,
                back TEXT NOT NULL,
                topic TEXT,
                is_completed INTEGER DEFAULT 0,
                FOREIGN KEY (task_id) REFERENCES micro_tasks(id)
            );

            CREATE TABLE IF NOT EXISTS ml_coding (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                prompt TEXT NOT NULL,
                starter_code TEXT,
                solution_code TEXT,
                topic TEXT,
                test_case TEXT,
                is_completed INTEGER DEFAULT 0,
                FOREIGN KEY (task_id) REFERENCES micro_tasks(id)
            );

            CREATE TABLE IF NOT EXISTS ml_quiz_booster (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                options TEXT,
                correct_answer TEXT,
                topic TEXT,
                is_completed INTEGER DEFAULT 0,
                FOREIGN KEY (task_id) REFERENCES micro_tasks(id)
            );

            CREATE TABLE IF NOT EXISTS mistake_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                quiz_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                question_id INTEGER,
                topic_tag TEXT DEFAULT '',
                mistake_summary TEXT DEFAULT '',
                quick_fix TEXT DEFAULT '',
                memory_trick TEXT DEFAULT '',
                recommended_topic TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (quiz_id) REFERENCES quizzes(id),
                FOREIGN KEY (class_id) REFERENCES classes(id)
            );

            -- ══ AUTH OTP TABLES ═════════════════════════════════════════

            -- Password reset OTP table
            CREATE TABLE IF NOT EXISTS password_reset_otp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                otp TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                used INTEGER DEFAULT 0,
                attempts INTEGER DEFAULT 0
            );

            -- OTP requests table (for signup and login verification)
            CREATE TABLE IF NOT EXISTS otp_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                otp_hash TEXT NOT NULL,
                otp_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                attempts INTEGER DEFAULT 0,
                is_used INTEGER DEFAULT 0
            );

            -- ══ EXAM ARENA TABLES ══════════════════════════════════════

            CREATE TABLE IF NOT EXISTS arena_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                exam TEXT NOT NULL DEFAULT 'JEE',
                subject TEXT NOT NULL DEFAULT 'Physics',
                mode TEXT NOT NULL DEFAULT 'Practice',
                preferred_difficulty TEXT NOT NULL DEFAULT 'Auto',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                UNIQUE(student_id)
            );

            CREATE TABLE IF NOT EXISTS arena_question_bank (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam TEXT NOT NULL,
                subject TEXT NOT NULL,
                topic_tag TEXT NOT NULL DEFAULT '',
                difficulty TEXT NOT NULL DEFAULT 'Medium',
                question_text TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_option TEXT NOT NULL,
                explanation TEXT NOT NULL DEFAULT '',
                estimated_time_seconds INTEGER NOT NULL DEFAULT 60,
                source_tag TEXT NOT NULL DEFAULT 'AI_GENERATED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS arena_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                exam TEXT NOT NULL,
                subject TEXT NOT NULL,
                attempt_type TEXT NOT NULL DEFAULT 'mock',
                difficulty_start TEXT DEFAULT 'Medium',
                difficulty_end TEXT DEFAULT 'Medium',
                score INTEGER NOT NULL DEFAULT 0,
                total_questions INTEGER NOT NULL DEFAULT 0,
                accuracy_percent REAL NOT NULL DEFAULT 0,
                avg_time_per_question REAL NOT NULL DEFAULT 0,
                time_taken_total INTEGER NOT NULL DEFAULT 0,
                xp_earned INTEGER NOT NULL DEFAULT 0,
                status TEXT DEFAULT 'ongoing', -- 'ongoing', 'completed', 'abandoned'
                questions_json TEXT DEFAULT '[]', -- List of Question IDs for this session
                current_q_index INTEGER DEFAULT 0, -- Resume state
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS arena_attempt_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                selected_option TEXT,
                is_correct INTEGER NOT NULL DEFAULT 0,
                time_taken_seconds REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (attempt_id) REFERENCES arena_attempts(id),
                FOREIGN KEY (question_id) REFERENCES arena_question_bank(id)
            );

            CREATE TABLE IF NOT EXISTS arena_topic_mastery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                exam TEXT NOT NULL,
                subject TEXT NOT NULL,
                topic_tag TEXT NOT NULL,
                mastery_score REAL NOT NULL DEFAULT 0,
                weak_flag INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                UNIQUE(student_id, exam, subject, topic_tag)
            );

            CREATE TABLE IF NOT EXISTS arena_rank_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                rank_name TEXT NOT NULL DEFAULT 'Bronze',
                xp_total INTEGER NOT NULL DEFAULT 0,
                streak_days INTEGER NOT NULL DEFAULT 0,
                last_daily_date TEXT DEFAULT '',
                readiness_score REAL NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                UNIQUE(student_id)
            );

            CREATE TABLE IF NOT EXISTS arena_ai_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                attempt_id INTEGER NOT NULL,
                topic_tag TEXT NOT NULL DEFAULT '',
                mistake_summary TEXT NOT NULL DEFAULT '',
                quick_fix TEXT NOT NULL DEFAULT '',
                memory_trick TEXT NOT NULL DEFAULT '',
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (attempt_id) REFERENCES arena_attempts(id)
            );

            CREATE TABLE IF NOT EXISTS arena_xp_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                source TEXT NOT NULL,  -- 'quiz', 'daily', 'bonus', 'achievement'
                description TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS arena_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                achievement_code TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                icon TEXT DEFAULT '🏆',
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                UNIQUE(student_id, achievement_code)
            );

            CREATE TABLE IF NOT EXISTS arena_missions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                mission_id TEXT NOT NULL,
                status TEXT DEFAULT 'locked', -- 'locked', 'unlocked', 'completed'
                stars INTEGER DEFAULT 0,
                score INTEGER DEFAULT 0,
                completed_at TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                UNIQUE(student_id, mission_id)
            );
            
            CREATE TABLE IF NOT EXISTS arena_revision_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                attempt_id INTEGER NOT NULL,
                exam TEXT NOT NULL,
                subject TEXT NOT NULL,
                mistake_summary TEXT DEFAULT '',
                revision_notes TEXT DEFAULT '',
                practice_questions TEXT DEFAULT '[]',
                topic_suggestions TEXT DEFAULT '[]',
                readiness_before REAL DEFAULT 0,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (attempt_id) REFERENCES arena_attempts(id)
            );

            -- Keep rank_status up to date with level info
            -- (Columns added via _add_column_if_missing below if needed)
        """)

        # ── Missing columns on existing tables ──────────────────────────

        # quizzes
        _add_column_if_missing(conn, 'quizzes', 'difficulty_level', 'TEXT')
        _add_column_if_missing(conn, 'quizzes', 'generated_by', 'INTEGER')
        _add_column_if_missing(conn, 'quizzes', 'module_id', 'INTEGER')

        # quiz_questions
        _add_column_if_missing(conn, 'quiz_questions', 'topic_tag', 'TEXT', "''")
        _add_column_if_missing(conn, 'quiz_questions', 'difficulty', 'TEXT', "''")

        # classes
        _add_column_if_missing(conn, 'classes', 'code', 'TEXT')
        _add_column_if_missing(conn, 'classes', 'subject', 'TEXT', "''")

        # student_module_progress — extra columns
        _add_column_if_missing(conn, 'student_module_progress', 'completion_percent', 'REAL', '0')
        _add_column_if_missing(conn, 'student_module_progress', 'quiz_score_avg', 'REAL', '0')

        # arena_rank_status
        _add_column_if_missing(conn, 'arena_rank_status', 'level', 'INTEGER', '1')
        _add_column_if_missing(conn, 'arena_rank_status', 'updated_at', 'TIMESTAMP')

        # arena_profiles
        _add_column_if_missing(conn, 'arena_profiles', 'updated_at', 'TIMESTAMP')

        # arena_attempts
        _add_column_if_missing(conn, 'arena_attempts', 'status', 'TEXT', "'ongoing'")
        _add_column_if_missing(conn, 'arena_attempts', 'questions_json', 'TEXT', "'[]'")
        _add_column_if_missing(conn, 'arena_attempts', 'current_q_index', 'INTEGER', '0')
        _add_column_if_missing(conn, 'arena_attempts', 'score', 'INTEGER', '0')
        _add_column_if_missing(conn, 'arena_attempts', 'xp_earned', 'INTEGER', '0')
        _add_column_if_missing(conn, 'arena_attempts', 'accuracy_percent', 'REAL', '0')
        _add_column_if_missing(conn, 'arena_attempts', 'total_questions', 'INTEGER', '0')
        _add_column_if_missing(conn, 'arena_attempts', 'avg_time_per_question', 'REAL', '0')
        _add_column_if_missing(conn, 'arena_attempts', 'updated_at', 'TIMESTAMP')
        _add_column_if_missing(conn, 'arena_attempts', 'created_at', 'TIMESTAMP')

        # arena_attempt_answers (Snapshot columns)
        _add_column_if_missing(conn, 'arena_attempt_answers', 'question_text', 'TEXT', "''")
        _add_column_if_missing(conn, 'arena_attempt_answers', 'option_a', 'TEXT', "''")
        _add_column_if_missing(conn, 'arena_attempt_answers', 'option_b', 'TEXT', "''")
        _add_column_if_missing(conn, 'arena_attempt_answers', 'option_c', 'TEXT', "''")
        _add_column_if_missing(conn, 'arena_attempt_answers', 'option_d', 'TEXT', "''")
        _add_column_if_missing(conn, 'arena_attempt_answers', 'correct_option', 'TEXT', "''")
        _add_column_if_missing(conn, 'arena_attempt_answers', 'explanation', 'TEXT', "''")

        # password_reset_otp — ensure all required columns exist on older tables
        _add_column_if_missing(conn, 'password_reset_otp', 'used', 'INTEGER', '0')
        _add_column_if_missing(conn, 'password_reset_otp', 'attempts', 'INTEGER', '0')
        _add_column_if_missing(conn, 'password_reset_otp', 'expires_at', 'TIMESTAMP')
        _add_column_if_missing(conn, 'password_reset_otp', 'created_at', 'TIMESTAMP')

        # otp_requests — ensure all required columns exist
        _add_column_if_missing(conn, 'otp_requests', 'attempts', 'INTEGER', '0')
        _add_column_if_missing(conn, 'otp_requests', 'is_used', 'INTEGER', '0')

        # Backfill timestamps for existing rows where they might be NULL
        conn.execute("UPDATE arena_attempts SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
        conn.execute("UPDATE arena_attempts SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")


        conn.commit()

        # ── Auto-generate learning modules for classes missing them ─────
        _auto_generate_learning_modules(conn)
        conn.commit()

        logger.info("Database schema migration completed successfully.")

    except Exception as e:
        logger.error(f"Schema migration error: {e}")
        raise
    finally:
        conn.close()
