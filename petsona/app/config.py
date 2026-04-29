import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def build_database_uri():
    """
    Build SQLAlchemy database URI from Railway environment variables.
    Supports both Railway (via MYSQLHOST etc.) and direct DATABASE_URI override.
    """
    # Check for explicit DATABASE_URI override first
    explicit_uri = os.getenv("DATABASE_URI")
    if explicit_uri:
        return explicit_uri
    
    # Build from Railway environment variables
    host = os.getenv("MYSQLHOST")
    port = os.getenv("MYSQLPORT", "21956")  # Default Railway MySQL port
    user = os.getenv("MYSQLUSER")
    password = os.getenv("MYSQLPASSWORD")
    database = os.getenv("MYSQLDATABASE")

    """
    # Ensure all required Railway variables are present
    if not all([host, user, password, database]):
        # Fallback for local development only
        if os.getenv("FLASK_ENV") != "production":
            host = host or "localhost"
            port = port or "3306"
            user = user or "root"
            password = password or "12345"
            database = database or "petsona"
        else:
            raise ValueError(
                "Missing Railway MySQL environment variables in production: "
                "MYSQLHOST, MYSQLPORT, MYSQLUSER, MYSQLPASSWORD, MYSQLDATABASE"
            )
    """
    
    # Build the URI with pymysql driver
    uri = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
    return uri


class Config:
    """Base config - safe defaults"""
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-dev-secret-key-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # Session & cookies - safest defaults
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Database Configuration (built dynamically from Railway env vars)
    SQLALCHEMY_DATABASE_URI = build_database_uri()

    # Mail Configuration (from environment variables)
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "False").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", MAIL_USERNAME)

    # =========================
    # GOOGLE OAUTH CONFIG (from environment variables)
    # =========================
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    
    # OAuth Settings
    AUTHLIB_INSECURE_TRANSPORT = os.getenv("AUTHLIB_INSECURE_TRANSPORT", "False").lower() == "true"

    # File Upload Configuration
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'messages')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max file size

    @staticmethod
    def init_app(app):
        """Initialize extensions with the app"""
        from app.extensions import oauth
        
        # Register Google OAuth only if credentials are provided
        if app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET"):
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
    AUTHLIB_INSECURE_TRANSPORT = True  # Allow HTTP for development

    # Password reset token expiry (seconds)
    RESET_TOKEN_EXPIRY = int(os.getenv("RESET_TOKEN_EXPIRY", 3600))


class ProductionConfig(Config):
    """Production config - secure defaults, Railway-optimized"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # must use HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    AUTHLIB_INSECURE_TRANSPORT = False  # Enforce HTTPS in production

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

    @staticmethod
    def init_app(app):
        """Initialize and validate production config"""
        Config.init_app(app)
        
        # Validate critical production environment variables
        required_vars = [
            ("MYSQLHOST", "Rswitchback.proxy.rlwy.net"),
            ("MYSQLUSER", "root"),
            ("MYSQLPASSWORD", "ErJDnYkJhYRtjKqDYcwQPLKfvbpNlIYP"),
            ("MYSQLDATABASE", "petsona"),
            ("MAIL_USERNAME", "jeysalas05@gmail.com"),
            ("MAIL_PASSWORD", "dvwj yvbl kqxu rbya"),
            ("SECRET_KEY", "your-super-secret-key-change-this-in-production"),
        ]
        
        missing_vars = []
        for var, description in required_vars:
            if not os.getenv(var):
                missing_vars.append(f"{var} ({description})")
        
        if missing_vars:
            raise ValueError(
                f"Missing required production environment variables:\n" +
                "\n".join(f"  - {var}" for var in missing_vars)
            )
