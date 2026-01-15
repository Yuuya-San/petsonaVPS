from flask_sqlalchemy import SQLAlchemy # pyright: ignore[reportMissingImports]
from flask_migrate import Migrate # pyright: ignore[reportMissingModuleSource]
from flask_login import LoginManager # pyright: ignore[reportMissingImports]
from flask_mail import Mail # pyright: ignore[reportMissingImports]
from flask_bcrypt import Bcrypt # pyright: ignore[reportMissingImports]
from flask_limiter import Limiter # pyright: ignore[reportMissingImports]
from flask_limiter.util import get_remote_address # pyright: ignore[reportMissingImports]
from flask_talisman import Talisman # pyright: ignore[reportMissingImports]
from flask_wtf import CSRFProtect

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
