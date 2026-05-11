from app import create_app, db
from app.models import *
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Default admin photo
DEFAULT_ADMIN_PHOTO = "images/logo/admin-avatar.png"

# Create Flask app and get Socket.IO instance
app, socketio = create_app()

# Ensure tables exist before querying for admin user
with app.app_context():
    from app.utils.db_init import create_tables
    create_tables(db)

    ADMIN_EMAIL = "petsona.helpcare@gmail.com"

    try:
        admin_exists = User.query.filter_by(email=ADMIN_EMAIL).first()
    except Exception:
        # Table might not exist yet
        create_tables(db)
        admin_exists = User.query.filter_by(email=ADMIN_EMAIL).first()

    if not admin_exists:
        user.create_admin(
            email=ADMIN_EMAIL,
            password="Petsona-0717",
            photo_url=DEFAULT_ADMIN_PHOTO
        )
        print(f"Default admin account created: {ADMIN_EMAIL} / Petsona-0717")
    else:
        print(f"Admin account already exists: {ADMIN_EMAIL}")

if __name__ == '__main__':
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))

    socketio.run(
        app,
        host=host,
        port=port,
        debug=True
    )

