"""Application factory. Initializes extensions, registers blueprints."""
from flask import Flask, redirect, url_for, request, flash, jsonify # pyright: ignore[reportMissingImports]
from werkzeug.exceptions import RequestEntityTooLarge, TooManyRequests # pyright: ignore[reportMissingImports]
from .config import Config
from app.extensions import db, migrate, login_manager, mail, bcrypt, limiter, talisman, socketio, oauth
from app.utils.db_init import ensure_database_exists, create_tables
from app.redis_manager import init_redis_for_socketio
from app.models import *
from .config import DevelopmentConfig, ProductionConfig
import os
from .config import get_config

def create_app(config_name='development'):
    app = Flask(__name__, static_folder="static", template_folder="templates")

    from werkzeug.middleware.proxy_fix import ProxyFix

    # CRITICAL: Include x_for=1 to properly handle X-Forwarded-For header
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_for=1, x_host=1)

    # Load config based on name
    if config_name == 'production':
        app.config.from_object(ProductionConfig)
        env = "production"
        async_mode = 'gevent'
    else:
        app.config.from_object(DevelopmentConfig)
        env = "development"
        async_mode = 'threading'

    # Session cookie settings - set AFTER config loading to ensure they take effect
    if env == "production":
        app.config["SESSION_COOKIE_SECURE"] = True
    else:
        app.config["SESSION_COOKIE_SECURE"] = False

    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Initialize extensions

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    bcrypt.init_app(app)
    limiter.init_app(app)
    talisman.init_app(app, force_https=False, content_security_policy=None)
    from app.extensions import csrf
    csrf.init_app(app)
    init_redis_for_socketio(app, socketio, async_mode)
    oauth.init_app(app)
    
    # Initialize QR Code generator
    from app.utils.qr_generator import qr_generator
    qr_generator.init_app(app)
    
    # Initialize config (including OAuth registration)
    get_config().init_app(app)

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

    # Custom Jinja2 filter for formatting datetime to human-readable PH timezone
    def format_ph_datetime(iso_datetime_str):
        """Format ISO datetime string to human-readable PH timezone format."""
        if not iso_datetime_str:
            return 'N/A'
        try:
            from datetime import datetime
            import pytz
            
            # Parse ISO format datetime string
            if isinstance(iso_datetime_str, str):
                # Handle ISO format with timezone (e.g., "2026-04-27T14:30:00+08:00")
                dt = datetime.fromisoformat(iso_datetime_str.replace('Z', '+00:00'))
            else:
                # If it's already a datetime object
                dt = iso_datetime_str
            
            # Ensure timezone-aware
            if dt.tzinfo is None:
                pht_tz = pytz.timezone('Asia/Manila')
                dt = pht_tz.localize(dt)
            
            # Format: "Apr 27, 2026 2:30 PM PHT"
            return dt.strftime('%b %d, %Y %I:%M %p')
        except Exception as e:
            print(f"[ERROR] Failed to format datetime: {e}")
            return str(iso_datetime_str)[:10] if iso_datetime_str else 'N/A'
    
    app.jinja_env.filters['format_ph_datetime'] = format_ph_datetime

    # Flask-Login user loader with error handling for database connection
    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = User.query.get(int(user_id))
            if user and user.has_temp_password:
                # Force logout users with temporary passwords
                import logging
                logging.warning(f"User {user_id} has temporary password - forcing logout")
                return None
            return user
        except Exception as e:
            # Log the error but don't crash the app
            import logging
            logging.error(f"❌ Error loading user {user_id}: {str(e)}")
            # Return None to treat as unauthenticated
            return None

    # Auto-create database and tables with error handling
    with app.app_context():
        try:
            ensure_database_exists()
            create_tables(db)
            print("✅ Database tables verified/created successfully")
        except Exception as e:
            import logging
            logging.error(f"❌ Database initialization error: {str(e)}")
            print(f"⚠️ WARNING: Database connection failed. Make sure MySQL is running.")
            print(f"   Error: {str(e)}")

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

    # NOTIFICATIONS API BLUEPRINT
    from .notifications_api import notifications_bp
    app.register_blueprint(notifications_bp)

    # ACCOUNT API BLUEPRINT
    from .account_api import bp as account_api_bp
    app.register_blueprint(account_api_bp)

    # SOCKET.IO EVENTS
    from . import socket_events

    # SOCKET.IO MONITORING
    from app.socket_monitoring import create_monitoring_blueprint
    monitoring_bp = create_monitoring_blueprint(app)
    app.register_blueprint(monitoring_bp)

    # TEMPLATE CONTEXT PROCESSORS
    @app.context_processor
    def inject_navbar_data():
        """Inject notifications and recent conversations into all templates."""
        from flask_login import current_user # pyright: ignore[reportMissingImports]
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

    # Global error handler for oversized multipart uploads
    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_entity_too_large(error):
        flash('Uploaded files exceed the maximum allowed upload size. Reduce attachments and try again.', 'danger')
        return redirect(request.referrer or url_for('merchant.apply'))

    # Global rate limit handler
    @app.errorhandler(TooManyRequests)
    def handle_rate_limit(error):
        message = 'Too many requests. Please slow down and try again in a few moments.'
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({
                'error': 'rate_limit_exceeded',
                'message': message,
                'retry_after': error.description if hasattr(error, 'description') else None
            }), 429

        flash(message, 'warning')
        return redirect(request.referrer or request.path)

    # Root route
    @app.route("/")
    def index():
        return redirect(url_for("auth.home"))

    return app, socketio
