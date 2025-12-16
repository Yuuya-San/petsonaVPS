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

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    bcrypt.init_app(app)
    limiter.init_app(app)
    talisman.init_app(app, content_security_policy=app.config.get("CSP", {}))

    # Flask-Login user loader
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Ensure session lifetime
    @app.before_request
    def make_session_permanent():
        from flask import session
        session.permanent = True

    # Auto-create database and tables
    with app.app_context():
        ensure_database_exists()
        create_tables(db)

    # AUTH BLUEPRINT
    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")

    # USER BLUEPRINT
    from .user import bp as user_bp
    app.register_blueprint(user_bp, url_prefix="/user")

    # ADMIN BLUEPRINT
    from .admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # MERCHANT BLUEPRINT
    from .merchant import bp as merchant_bp
    app.register_blueprint(merchant_bp, url_prefix="/merchant")

    # PETS BLUEPRINT
    from .pets import bp as pets_bp
    app.register_blueprint(pets_bp, url_prefix="/pets")

    # Root route
    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    return app
