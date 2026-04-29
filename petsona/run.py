from app import create_app, db
from app.models import *
import os

# Default admin photo
DEFAULT_ADMIN_PHOTO = "images/avatar/avatar-12.png",

# Create Flask app and get Socket.IO instance
app, socketio = create_app()

# Ensure tables exist before querying for admin user
with app.app_context():
    from app.utils.db_init import create_tables
    create_tables(db)

    ADMIN_EMAIL = "petsona.helpcare@gmail.com"
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Petsona-0717")  # Change in production!

    try:
        admin_exists = User.query.filter_by(email=ADMIN_EMAIL).first()
    except Exception:
        # Table might not exist yet
        create_tables(db)
        admin_exists = User.query.filter_by(email=ADMIN_EMAIL).first()

    if not admin_exists:
        user.create_admin(
            email=ADMIN_EMAIL,
            password=ADMIN_PASSWORD,
            photo_url=DEFAULT_ADMIN_PHOTO
        )
        print(f"Default admin account created: {ADMIN_EMAIL}")
        print(f"⚠️  WARNING: Change the default password immediately in production!")
    else:
        print(f"Admin account already exists: {ADMIN_EMAIL}")

if __name__ == '__main__':
    is_production = os.getenv("FLASK_ENV") == "production"
    
    if is_production:
        print("⚠️  PRODUCTION MODE: Do NOT use the development server!")
        print("    Use Gunicorn with: gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 'run:app'")
        print("    Or with python-socketio: gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 'run:app'")
        # Still run for testing, but with production settings
        socketio.run(app, host='127.0.0.1', port=5000, debug=False, allow_unsafe_werkzeug=False)
    else:
        # Development server - debug enabled for local testing
        socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)

