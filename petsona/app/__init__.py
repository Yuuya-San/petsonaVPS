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

    # Custom Jinja2 filter for converting operating days from numeric to names
    def convert_operating_days(operating_days_str):
        """Convert operating days from numeric string/list to day names."""
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        if not operating_days_str:
            return 'N/A'
        try:
            # Handle both string and list inputs
            if isinstance(operating_days_str, str):
                days = [int(d.strip()) for d in operating_days_str.split(',')]
            else:
                days = [int(d) for d in operating_days_str]
            
            day_list = [day_names[d] for d in days if 0 <= d < 7]
            return ', '.join(day_list) if day_list else 'N/A'
        except (ValueError, TypeError, IndexError):
            return 'N/A'
    
    app.jinja_env.filters['operating_days'] = convert_operating_days

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

    # MESSAGES BLUEPRINT
    from .messages import bp as messages_bp
    app.register_blueprint(messages_bp)

    # VOTES API BLUEPRINT
    from .votes import votes_bp
    app.register_blueprint(votes_bp)

    # SOCKET.IO EVENTS
    from . import socket_events

    # TEMPLATE CONTEXT PROCESSORS
    @app.context_processor
    def inject_navbar_data():
        """Inject notifications and recent conversations into all templates."""
        from flask_login import current_user
        from app.utils.messaging import get_user_inbox, get_unread_count
        
        notifications = []
        recent_conversations = []
        unread_count = 0
        
        if current_user.is_authenticated:
            try:
                # Get unread message count
                unread_count = get_unread_count(current_user.id)
                
                # Get recent conversations (first 5)
                inbox_pagination = get_user_inbox(current_user.id, page=1, per_page=8, include_archived=False)
                recent_conversations = inbox_pagination.items if inbox_pagination and inbox_pagination.items else []
                
                # Get notifications (empty list for now - can be expanded later)
                notifications = []
            except Exception as e:
                # Silently fail if there's an error - log for debugging
                import logging
                logging.error(f"Error in inject_navbar_data: {e}")
                recent_conversations = []
                unread_count = 0
        
        return dict(
            notifications=notifications,
            recent_conversations=recent_conversations,
            unread_badge_count=unread_count
        )

    # Root route
    @app.route("/")
    def index():
        return redirect(url_for("auth.home"))

    return app, socketio
