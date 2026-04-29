import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base config - safe defaults"""
    SECRET_KEY = os.getenv("SECRET_KEY") or "fallback-very-strong-key"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # Session & cookies - safest defaults
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

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
    MAIL_PASSWORD = "dvwj yvbl kqxu rbya"  # your Gmail app password
    MAIL_DEFAULT_SENDER = "jeysalas05@gmail.com"

    # =========================
    # GOOGLE OAUTH CONFIG
    # =========================
    GOOGLE_CLIENT_ID = "465984026247-mcqjo45k0dqcrsn9rmf1o9dp0vaqjbbn.apps.googleusercontent.com"
    GOOGLE_CLIENT_SECRET = "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"
    
    # OAuth Settings
    AUTHLIB_INSECURE_TRANSPORT = True  # Allow HTTP for development

    # File Upload Configuration
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'messages')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max file size

    @staticmethod
    def init_app(app):
        """Initialize extensions with the app"""
        from app.extensions import oauth
        
        # Register Google OAuth
        oauth.register(
            name="google",
            client_id=app.config.get("GOOGLE_CLIENT_ID"),
            client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={
                "scope": "openid email profile"
            }
        )

    
class DevelopmentConfig(Config):
    """Development config - allow insecure cookies on HTTP dev"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False  # safe for localhost dev
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI", "mysql+pymysql://root:12345@localhost/petsona")

    # Password reset token expiry (seconds)
    RESET_TOKEN_EXPIRY = int(os.getenv("RESET_TOKEN_EXPIRY", 3600))


class ProductionConfig(Config):
    """Production config - secure defaults"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # must use HTTPS
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI", "mysql+pymysql://root:12345@localhost/petsona")

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
