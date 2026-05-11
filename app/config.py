import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base config - safe defaults"""
    SECRET_KEY = os.getenv("SECRET_KEY") or "fallback-very-strong-key"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    PREFERRED_URL_SCHEME = "https"

    # Session & cookies - safest defaults
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URI",
        "mysql+pymysql://petsona_user:Petsona-0717@localhost/petsona_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    RATELIMIT_STORAGE_URI = "redis://localhost:6379/2"
    
    # Mail
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "False").lower() in ("true", "1", "yes")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "jeysalas05@gmail.com")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "dvwj yvbl kqxu rbya")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", MAIL_USERNAME)
    
    # Redis / Socket.IO queue
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    SOCKETIO_USE_REDIS = os.getenv("SOCKETIO_USE_REDIS", "False").lower() in ("true", "1", "yes")
    SOCKETIO_REDIS_URL = os.getenv("SOCKETIO_REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/1"))

    # =========================
    # GOOGLE OAUTH CONFIG
    # =========================
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "246292318836-fh4abergpjnerh6nj55plpr0lusrqu0q.apps.googleusercontent.com")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "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")
    
    # OAuth Settings
    AUTHLIB_INSECURE_TRANSPORT = os.getenv("AUTHLIB_INSECURE_TRANSPORT", "False").lower() in ("true", "1", "yes")

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
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URI",
        "mysql+pymysql://petsona_user:Petsona-0717@localhost/petsona_db"
    )
    AUTHLIB_INSECURE_TRANSPORT = True

    # Password reset token expiry (seconds)
    RESET_TOKEN_EXPIRY = int(os.getenv("RESET_TOKEN_EXPIRY", 3600))


class ProductionConfig(Config):
    """Production config - secure defaults"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # must use HTTPS
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URI",
        "mysql+pymysql://petsona_user:Petsona-0717@localhost/petsona_db"
    )

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
