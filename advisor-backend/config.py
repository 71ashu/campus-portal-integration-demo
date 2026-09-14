"""Application configuration."""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # SQLite keeps this demo a `pip install && python app.py` away from running
    # anywhere, with no external database to stand up. Pinned to an absolute
    # path next to this file — Flask-SQLAlchemy otherwise resolves a relative
    # sqlite:/// URI against app.instance_path (an `instance/` folder), not
    # the working directory, which is an easy place to lose track of the db.
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL', f"sqlite:///{os.path.join(BASE_DIR, 'advisor.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173').rstrip('/')

    # --- Mock SIS integration ---
    SIS_BASE_URL = os.getenv('SIS_BASE_URL', 'http://localhost:5050').rstrip('/')
    SIS_PROGRAM_ID = os.getenv('SIS_PROGRAM_ID', 'BS-CS-2024')
    # Shared secret the mock SIS must present when it calls our webhook, and
    # that our own /api/auth/sso trusts as a stand-in for a real SSO handshake.
    # Left empty by default so the demo runs unconfigured; set it to anything
    # non-empty to require the header on both sides.
    SIS_WEBHOOK_TOKEN = os.getenv('SIS_WEBHOOK_TOKEN', '')

    _dev_origins = ['http://localhost:5173', 'http://127.0.0.1:5173']
    CORS_ORIGINS = (
        [FRONTEND_URL] if FLASK_ENV == 'production'
        else sorted({FRONTEND_URL, *_dev_origins})
    )
