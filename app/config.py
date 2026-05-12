import os
from datetime import timedelta

class Config:
    """Base config - shared settings"""

    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-very-strong-key")

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    PREFERRED_URL_SCHEME = "http"

    # Session & cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_REFRESH_EACH_REQUEST = False

    # Connection pooling
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 20,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
        "max_overflow": 40,
        "connect_args": {
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
            "autocommit": False,
        },
    }

    # Redis
    REDIS_URL = "redis://localhost:6379/0"

    RATELIMIT_STORAGE_URI = "redis://localhost:6379/2"


    # Mail
    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = "True"
    MAIL_USE_SSL = "False"
    MAIL_USERNAME = "petsona.helpcare@gmail.com"
    MAIL_PASSWORD = "fvgj yfgi aulq squa"
    MAIL_DEFAULT_SENDER = MAIL_USERNAME

    # Socket.IO
    SOCKETIO_USE_REDIS = "False"
    SOCKETIO_REDIS_URL = "redis://localhost:6379/1"

    # Google OAuth
    GOOGLE_CLIENT_ID = "246292318836-fh4abergpjnerh6nj55plpr0lusrqu0q.apps.googleusercontent.com"
    GOOGLE_CLIENT_SECRET = "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"
    
    # reCAPTCHA Configuration
    RECAPTCHA_SITE_KEY = "6Le4c94sAAAAADh1YOljhLnxWDxvrMbGCDzSXcWT"
    RECAPTCHA_SECRET_KEY = "6Le4c94sAAAAAHVDiFrjrGYM6c6bdBs0KhnS72VN"

    AUTHLIB_INSECURE_TRANSPORT = "False"

    # Uploads
    UPLOAD_FOLDER = os.path.join(
        os.path.dirname(__file__),
        "static",
        "uploads",
        "messages"
    )

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    @staticmethod
    def init_app(app):
        """Initialize extensions with the app"""

        from app.extensions import oauth

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
    """Development config"""

    DEBUG = True

    SESSION_COOKIE_SECURE = False

    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:Petsona-0717@localhost/petsona"

    AUTHLIB_INSECURE_TRANSPORT = True

    RESET_TOKEN_EXPIRY = 3600

class ProductionConfig(Config):
    """Production config"""

    DEBUG = False

    SESSION_COOKIE_SECURE = True

    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://petsona_user:Petsona-0717@localhost/petsona_db"


    RESET_TOKEN_EXPIRY = 3600

    RATELIMIT_DEFAULT = "200 per day"
    RATELIMIT_STRATEGY = "fixed-window"

    MAX_FAILED_LOGIN = 5

    LOCKOUT_TIME = 300

    CSP = {
        "default-src": ["'self'"],

        "script-src": [
            "'self'",
            "'unsafe-inline'",
            "'unsafe-eval'",
            "https://www.google.com",
            "https://www.gstatic.com",
            "https://www.recaptcha.net"
        ],

        "style-src": [
            "'self'",
            "'unsafe-inline'",
            "https://fonts.googleapis.com",
            "https://cdnjs.cloudflare.com"
        ],

        "font-src": [
            "'self'",
            "https://fonts.gstatic.com",
            "https://cdnjs.cloudflare.com",
            "data:"
        ],

        "frame-src": [
            "'self'",
            "https://www.google.com",
            "https://www.recaptcha.net"
        ],

        "connect-src": [
            "'self'",
            "https://www.google.com",
            "https://www.gstatic.com",
            "https://www.recaptcha.net"
        ],

        "img-src": [
            "'self'",
            "data:",
            "blob:",
            "https://www.google.com",
            "https://www.gstatic.com",
            "https://www.recaptcha.net"
        ]
    }

    FRONTEND_URL = None


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config():
    env = "development"
    return config_by_name.get(env, DevelopmentConfig)