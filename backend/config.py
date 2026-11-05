import os
from datetime import timedelta
from dotenv import load_dotenv

# Ensure .env is loaded from project root
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
load_dotenv(dotenv_path=ENV_PATH)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "deepfake-v2-dev-fallback-secret-key-39f82d1a")

    # PostgreSQL Database URL
    raw_db_url = os.getenv("DATABASE_URL")
    if not raw_db_url:
        raise ValueError(
            "DATABASE_URL is not set in the environment or .env file. "
            "Please check .env or refer to .env.example."
        )

    # Standardize postgres:// to postgresql:// for SQLAlchemy compatibility
    if raw_db_url.startswith("postgres://"):
        raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = raw_db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Session & Cookie Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("FLASK_ENV") == "production"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = timedelta(days=14)

    # WTForms CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Uploads
    UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
