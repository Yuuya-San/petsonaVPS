from flask_sqlalchemy import SQLAlchemy # pyright: ignore[reportMissingImports]
from flask_migrate import Migrate # pyright: ignore[reportMissingModuleSource]
from flask_login import LoginManager # pyright: ignore[reportMissingImports]
from flask_mail import Mail # pyright: ignore[reportMissingImports]
from flask_bcrypt import Bcrypt # pyright: ignore[reportMissingImports]
from flask_limiter import Limiter # pyright: ignore[reportMissingImports]
from flask_limiter.util import get_remote_address # pyright: ignore[reportMissingImports]
from flask_talisman import Talisman # pyright: ignore[reportMissingImports]
from flask_wtf import CSRFProtect
from flask_socketio import SocketIO # pyright: ignore[reportMissingImports]
from authlib.integrations.flask_client import OAuth # pyright: ignore[reportMissingImports]

# Database + migrations
db = SQLAlchemy()
migrate = Migrate()

# Login manager
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.session_protection = "strong"

# Mail
mail = Mail()

# Bcrypt for secure password hashing
bcrypt = Bcrypt()

# Rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)


# Security headers / HSTS
talisman = Talisman()

# CSRF protection
csrf = CSRFProtect()

# Socket.IO for real-time updates - Production-ready with eventlet
# Uses eventlet for high-performance async I/O and greenlet concurrency
socketio = SocketIO(
    # Performance optimizations
    async_mode='eventlet',  # High-performance async mode (matches production guide)
    cors_allowed_origins="*",
    
    # Connection parameters
    ping_timeout=120,  # Timeout before disconnecting idle clients
    ping_interval=30,  # Server-side ping interval
    
    # Transport optimization - WebSocket only in production (no polling overhead)
    # Polling is disabled in production to reduce unnecessary requests
    transports=['websocket'],
    
    # Message compression for bandwidth reduction
    compress=True,
    
    # Connection queue management
    max_http_buffer_size=1e8,  # 100MB max message size
    
    # Disable debug logging for performance
    engineio_logger=False,
    logger=False,
    
    # Connection state management
    manage_acks=True,  # Track message acknowledgments
)

# OAuth for social login
oauth = OAuth()
