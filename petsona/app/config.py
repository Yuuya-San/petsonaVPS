# app/config.py
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    DB_HOST = "localhost"
    DB_NAME = "petsona"
    DB_USERNAME = "root"
    DB_PASSWORD = "12345"

    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    

    # Mail
    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False  # TLS is enough
    MAIL_USERNAME = "jeysalas05@gmail.com"
    MAIL_PASSWORD = "whgtlvnqajqmipfc"  # your Gmail app password
    MAIL_DEFAULT_SENDER = "jeysalas05@gmail.com"


    # Session & cookies
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_DURATION = timedelta(days=7)

    # Password reset token expiry (seconds)
    RESET_TOKEN_EXPIRY = int(os.getenv("RESET_TOKEN_EXPIRY", 3600))

    # Rate limiting defaults
    RATELIMIT_DEFAULT = "200 per day"
    RATELIMIT_STRATEGY = "fixed-window"

    # Account lockout policy
    MAX_FAILED_LOGIN = int(os.getenv("MAX_FAILED_LOGIN", 5))
    LOCKOUT_TIME = int(os.getenv("LOCKOUT_TIME", 300))  # seconds

    # CSP (restrictive - adjust if you load external assets)
    CSP = {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "style-src": ["'self'", "https://fonts.googleapis.com"],
        "font-src": ["'self'", "https://fonts.gstatic.com"],
        "img-src": ["'self'", "data:"],
    }

    # Optional frontend base used for reset links (if you want frontend separate)
    FRONTEND_URL = os.getenv("FRONTEND_URL", None)
