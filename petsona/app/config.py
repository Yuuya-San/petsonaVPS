import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _get_required_env(key: str, config_name: str = "config") -> str:
    """Get required environment variable or raise helpful error"""
    value = os.getenv(key)
    if not value:
        raise ValueError(
            f"Missing required environment variable: {key}\n"
            f"Please set {key} in your .env file or environment."
        )
    return value


class Config:
    """Base config - safe defaults for all environments"""
    
    # ========================
    # CORE APPLICATION CONFIG
    # ========================
    SECRET_KEY = _get_required_env("SECRET_KEY")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    
    # Session & cookies - strict defaults
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    
    # ========================
    # DATABASE CONFIG
    # ========================
    SQLALCHEMY_DATABASE_URI = _get_required_env("DATABASE_URI")
    
    # ========================
    # EMAIL CONFIG
    # ========================
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "False").lower() == "true"
    MAIL_USERNAME = _get_required_env("MAIL_USERNAME")
    MAIL_PASSWORD = _get_required_env("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = _get_required_env("MAIL_DEFAULT_SENDER")
    
    # ========================
    # GOOGLE OAUTH CONFIG
    # ========================
    GOOGLE_CLIENT_ID = _get_required_env("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = _get_required_env("GOOGLE_CLIENT_SECRET")
    
    # ========================
    # FILE UPLOAD CONFIG
    # ========================
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'messages')
    MAX_CONTENT_LENGTH = 13 * 1024 * 1024  # 13MB max request size
    
    # ========================
    # SECURITY CONFIG
    # ========================
    MAX_FAILED_LOGIN = int(os.getenv("MAX_FAILED_LOGIN", 5))
    LOCKOUT_TIME = int(os.getenv("LOCKOUT_TIME", 300))  # seconds
    RESET_TOKEN_EXPIRY = int(os.getenv("RESET_TOKEN_EXPIRY", 3600))  # seconds
    
    # ========================
    # RATE LIMITING
    # ========================
    RATELIMIT_DEFAULT = "200 per day"
    RATELIMIT_STRATEGY = "fixed-window"
    
    # ========================
    # CSP HEADERS
    # ========================
    CSP = {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "style-src": ["'self'", "https://fonts.googleapis.com"],
        "font-src": ["'self'", "https://fonts.gstatic.com"],
        "img-src": ["'self'", "data:"],
    }
    
    # Optional frontend URL for reset/confirmation links
    FRONTEND_URL = os.getenv("FRONTEND_URL", None)

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
    """Development config - relaxed for local development"""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False  # safe for localhost dev
    # Allow insecure transport only for local OAuth testing
    AUTHLIB_INSECURE_TRANSPORT = True


class ProductionConfig(Config):
    """Production config - strict security defaults"""
    DEBUG = False
    TESTING = False
    
    # Enforce HTTPS for cookies and OAuth
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = True
    
    # Never allow insecure transport in production
    AUTHLIB_INSECURE_TRANSPORT = False


class TestingConfig(Config):
    """Testing config"""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    AUTHLIB_INSECURE_TRANSPORT = True
