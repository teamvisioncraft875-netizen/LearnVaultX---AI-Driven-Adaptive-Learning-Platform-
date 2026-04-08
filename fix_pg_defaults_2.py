import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
pg_url = os.getenv('DATABASE_URL')
conn = psycopg2.connect(pg_url)
cur = conn.cursor()

defaults = [
    # arena_attempt_answers
    "ALTER TABLE arena_attempt_answers ALTER COLUMN is_correct SET DEFAULT 0;",
    "ALTER TABLE arena_attempt_answers ALTER COLUMN time_taken_seconds SET DEFAULT 0;",
    "ALTER TABLE arena_attempt_answers ALTER COLUMN question_text SET DEFAULT '';",
    "ALTER TABLE arena_attempt_answers ALTER COLUMN option_a SET DEFAULT '';",
    "ALTER TABLE arena_attempt_answers ALTER COLUMN option_b SET DEFAULT '';",
    "ALTER TABLE arena_attempt_answers ALTER COLUMN option_c SET DEFAULT '';",
    "ALTER TABLE arena_attempt_answers ALTER COLUMN option_d SET DEFAULT '';",
    "ALTER TABLE arena_attempt_answers ALTER COLUMN correct_option SET DEFAULT '';",
    "ALTER TABLE arena_attempt_answers ALTER COLUMN explanation SET DEFAULT '';",

    # other arena tables
    "ALTER TABLE arena_xp_log ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE arena_xp_log ALTER COLUMN description SET DEFAULT '';",
    "ALTER TABLE arena_achievements ALTER COLUMN unlocked_at SET DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE arena_achievements ALTER COLUMN description SET DEFAULT '';",
    "ALTER TABLE arena_revision_plans ALTER COLUMN generated_at SET DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE arena_revision_plans ALTER COLUMN mistake_summary SET DEFAULT '';",
    "ALTER TABLE arena_revision_plans ALTER COLUMN revision_notes SET DEFAULT '';",
    "ALTER TABLE arena_revision_plans ALTER COLUMN practice_questions SET DEFAULT '[]';",
    "ALTER TABLE arena_revision_plans ALTER COLUMN topic_suggestions SET DEFAULT '[]';",
    "ALTER TABLE arena_revision_plans ALTER COLUMN readiness_before SET DEFAULT 0;",
    
    "ALTER TABLE arena_ai_notes ALTER COLUMN generated_at SET DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE arena_ai_notes ALTER COLUMN mistake_summary SET DEFAULT '';",
    "ALTER TABLE arena_ai_notes ALTER COLUMN quick_fix SET DEFAULT '';",
    "ALTER TABLE arena_ai_notes ALTER COLUMN memory_trick SET DEFAULT '';",
    "ALTER TABLE arena_ai_notes ALTER COLUMN topic_tag SET DEFAULT '';",

    "ALTER TABLE arena_rank_status ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE arena_topic_mastery ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE arena_profiles ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE arena_attempts ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE arena_attempts ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;",

    "ALTER TABLE arena_question_bank ALTER COLUMN topic_tag SET DEFAULT '';",
    "ALTER TABLE arena_question_bank ALTER COLUMN difficulty SET DEFAULT 'Medium';",
    "ALTER TABLE arena_question_bank ALTER COLUMN explanation SET DEFAULT '';",
    "ALTER TABLE arena_question_bank ALTER COLUMN estimated_time_seconds SET DEFAULT 60;",
    "ALTER TABLE arena_question_bank ALTER COLUMN source_tag SET DEFAULT 'AI_GENERATED';",
    "ALTER TABLE arena_question_bank ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;",

    # auth and others
    "ALTER TABLE password_reset_otp ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE otp_requests ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;",
]

for cmd in defaults:
    try:
        cur.execute(cmd)
    except Exception as e:
        print(f"Skipping: {cmd} -> {e}")
        conn.rollback()
    else:
        conn.commit()

print("Schema defaults completely fixed part 2.")
