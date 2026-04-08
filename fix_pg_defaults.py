import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
pg_url = os.getenv('DATABASE_URL')
conn = psycopg2.connect(pg_url)
cur = conn.cursor()

defaults = [
    # arena_attempts
    "ALTER TABLE arena_attempts ALTER COLUMN score SET DEFAULT 0;",
    "ALTER TABLE arena_attempts ALTER COLUMN total_questions SET DEFAULT 0;",
    "ALTER TABLE arena_attempts ALTER COLUMN accuracy_percent SET DEFAULT 0;",
    "ALTER TABLE arena_attempts ALTER COLUMN avg_time_per_question SET DEFAULT 0;",
    "ALTER TABLE arena_attempts ALTER COLUMN time_taken_total SET DEFAULT 0;",
    "ALTER TABLE arena_attempts ALTER COLUMN xp_earned SET DEFAULT 0;",
    "ALTER TABLE arena_attempts ALTER COLUMN current_q_index SET DEFAULT 0;",
    "ALTER TABLE arena_attempts ALTER COLUMN status SET DEFAULT 'ongoing';",
    "ALTER TABLE arena_attempts ALTER COLUMN questions_json SET DEFAULT '[]';",
    "ALTER TABLE arena_attempts ALTER COLUMN attempt_type SET DEFAULT 'mock';",
    "ALTER TABLE arena_attempts ALTER COLUMN difficulty_start SET DEFAULT 'Medium';",
    "ALTER TABLE arena_attempts ALTER COLUMN difficulty_end SET DEFAULT 'Medium';",

    # ranks
    "ALTER TABLE arena_rank_status ALTER COLUMN xp_total SET DEFAULT 0;",
    "ALTER TABLE arena_rank_status ALTER COLUMN streak_days SET DEFAULT 0;",
    "ALTER TABLE arena_rank_status ALTER COLUMN readiness_score SET DEFAULT 0;",
    
    # mastery
    "ALTER TABLE arena_topic_mastery ALTER COLUMN mastery_score SET DEFAULT 0;",
    "ALTER TABLE arena_topic_mastery ALTER COLUMN weak_flag SET DEFAULT 0;",

    # missions
    "ALTER TABLE arena_missions ALTER COLUMN status SET DEFAULT 'locked';",
    "ALTER TABLE arena_missions ALTER COLUMN stars SET DEFAULT 0;",
    "ALTER TABLE arena_missions ALTER COLUMN score SET DEFAULT 0;",

    # auth
    "ALTER TABLE otp_requests ALTER COLUMN attempts SET DEFAULT 0;",
    "ALTER TABLE otp_requests ALTER COLUMN is_used SET DEFAULT 0;",
    "ALTER TABLE password_reset_otp ALTER COLUMN used SET DEFAULT 0;",
    "ALTER TABLE password_reset_otp ALTER COLUMN attempts SET DEFAULT 0;",

    # learning
    "ALTER TABLE student_module_progress ALTER COLUMN completion_percent SET DEFAULT 0;",
    "ALTER TABLE student_module_progress ALTER COLUMN quiz_score_avg SET DEFAULT 0;",
    "ALTER TABLE student_skill_progress ALTER COLUMN score SET DEFAULT 0;",
]

for cmd in defaults:
    try:
        cur.execute(cmd)
    except psycopg2.Error as e:
        print(f"Skipping (might not exist): {cmd}")
        conn.rollback()
    else:
        conn.commit()

print("Schema defaults completely fixed.")
