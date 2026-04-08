"""
Application configuration for LearnVaultX.
Loads settings from environment variables via python-dotenv.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""

    # Flask
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-change-in-production')
    APP_VERSION = '2.0.2'

    # Session Cookies
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True

    # Database — PostgreSQL via SQLAlchemy
    DATABASE_URL = os.environ.get(
        'DATABASE_URL',
        'postgresql://postgres:postgres@localhost:5432/learnvaultx'
    )
    # Fix for Render / Heroku which use 'postgres://' (deprecated by SQLAlchemy)
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_size': 5,
        'max_overflow': 10,
    }

    # File Uploads (moved outside of static directory)
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'uploads')
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB

    # External services (loaded from env)
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
    SMTP_EMAIL = os.environ.get('SMTP_EMAIL', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
    JITSI_DOMAIN = os.environ.get('JITSI_DOMAIN', 'meet.jit.si')
