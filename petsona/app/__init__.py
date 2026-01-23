"""Application factory. Initializes extensions, registers blueprints."""
from flask import Flask, redirect, url_for
from .config import Config
from app.extensions import db, migrate, login_manager, mail, bcrypt, limiter, talisman, socketio, oauth
from app.utils.db_init import ensure_database_exists, create_tables

# Import User model for login manager
from app.models import *
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
    else:
        app.config.from_object(DevelopmentConfig)

    # Initialize extensions

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    bcrypt.init_app(app)
    limiter.init_app(app)
    talisman.init_app(app, content_security_policy=app.config.get("CSP", {}))
    from app.extensions import csrf
    csrf.init_app(app)
    socketio.init_app(app)
    oauth.init_app(app)
    
    # Initialize config (including OAuth registration)
    config_class.init_app(app)

    # Flask-Login user loader
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

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

    # PROFILE BLUEPRINT
    from .profile import bp as profile_bp
    app.register_blueprint(profile_bp, url_prefix="/profile")

    # PET MATCHING BLUEPRINT
    from .matching import bp as matching_bp
    app.register_blueprint(matching_bp, url_prefix="/matching")

    # VOTES API BLUEPRINT
    from .votes import votes_bp
    app.register_blueprint(votes_bp)

    # SOCKET.IO EVENTS
    from . import socket_events

    # Root route
    @app.route("/")
    def index():
        return redirect(url_for("auth.home"))

    return app, socketio
