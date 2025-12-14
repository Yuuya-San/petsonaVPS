"""Application factory. Initializes extensions, registers blueprints."""
from flask import Flask, redirect, url_for
from flask_login import current_user
from .config import Config
from .extensions import db, migrate, login_manager, mail, bcrypt, limiter, talisman
from app.utils.db_init import ensure_database_exists, create_tables

# Import User model for login manager
from .models import User
from .config import DevelopmentConfig, ProductionConfig
import os

def create_app(config_class: type = Config):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    # Always load base config first
    app.config.from_object(config_class)
    # Then override with environment-specific config
    env = os.getenv("FLASK_ENV", "development")
    if env == "production":
        app.config.from_object(ProductionConfig)
        ProductionConfig.init_app(app)
    else:
        app.config.from_object(DevelopmentConfig)
        DevelopmentConfig.init_app(app)

    # Initialize extensions after config is finalized
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    bcrypt.init_app(app)
    limiter.init_app(app)
    talisman.init_app(app, content_security_policy=app.config.get("CSP", {}))

    # Add Flask-Login user loader
    @login_manager.user_loader
    def load_user(user_id):
        """
        Flask-Login callback to load a user from the session.
        """
        return User.query.get(int(user_id))

    # Set session.permanent = True on every request to ensure session lifetime is respected
    @app.before_request
    def make_session_permanent():
        from flask import session
        session.permanent = True

    # Auto-create database and tables
    with app.app_context():
        ensure_database_exists()  # Creates DB if missing
        create_tables(db)         # Creates tables if missing

    # Register auth blueprint
    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")

    # Connect root to auth login
    @app.route("/")
    def index():
        """
        Redirect users to the login page.
        If you add a dashboard later, you can check if current_user.is_authenticated
        """
        return redirect(url_for("auth.login"))

    return app
