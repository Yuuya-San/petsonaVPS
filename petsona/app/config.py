import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration (used by both dev and prod)"""

    # =========================
    # CORE SECURITY
    # =========================
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-very-strong-key")

    # =========================
    # DATABASE (FIXED FOR RENDER)
    # =========================
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:12345@localhost/petsona"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # =========================
    # SESSION SECURITY
    # =========================
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # =========================
    # MAIL CONFIG
    # =========================
    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False

    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "jeysalas05@gmail.com")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "dvwj yvbl kqxu rbya")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_USERNAME", "jeysalas05@gmail.com")

    # =========================
    # GOOGLE OAUTH
    # =========================
    GOOGLE_CLIENT_ID = os.getenv("465984026247-mcqjo45k0dqcrsn9rmf1o9dp0vaqjbbn.apps.googleusercontent.com")
    GOOGLE_CLIENT_SECRET = os.getenv("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")
    AUTHLIB_INSECURE_TRANSPORT = True  # allow HTTP in dev

    # =========================
    # FILE UPLOAD
    # =========================
    UPLOAD_FOLDER = os.path.join(
        os.path.dirname(__file__),
        "static",
        "uploads",
        "messages"
    )
    MAX_CONTENT_LENGTH = 13 * 1024 * 1024  # 13MB

    # =========================
    # INIT EXTENSIONS
    # =========================
    @staticmethod
    def init_app(app):
        from app.extensions import oauth

        oauth.register(
            name="google",
            client_id=app.config.get("GOOGLE_CLIENT_ID"),
            client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"}
        )


# =========================
# DEVELOPMENT CONFIG
# =========================
class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


# =========================
# PRODUCTION CONFIG
# =========================
class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True

    REMEMBER_COOKIE_DURATION = timedelta(days=7)

    # Rate limiting
    RATELIMIT_DEFAULT = "200 per day"
    RATELIMIT_STRATEGY = "fixed-window"

    # Security controls
    MAX_FAILED_LOGIN = int(os.getenv("MAX_FAILED_LOGIN", 5))
    LOCKOUT_TIME = int(os.getenv("LOCKOUT_TIME", 300))  # seconds

    # Password reset expiry
    RESET_TOKEN_EXPIRY = int(os.getenv("RESET_TOKEN_EXPIRY", 3600))

    # Content Security Policy (if used in app)
    CSP = {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "style-src": ["'self'", "https://fonts.googleapis.com"],
        "font-src": ["'self'", "https://fonts.gstatic.com"],
        "img-src": ["'self'", "data:"],
    }

    FRONTEND_URL = os.getenv("FRONTEND_URL", None)
