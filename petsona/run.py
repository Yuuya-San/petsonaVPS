from app import create_app, db
from app.models import User, create_admin

# Default admin photo
DEFAULT_ADMIN_PHOTO = "images/avatar/dog.png"

# Create Flask app
app = create_app()

# Ensure tables exist before querying for admin user
with app.app_context():
    from app.utils.db_init import create_tables
    create_tables(db)

    ADMIN_EMAIL = "jeysalas05@gmail.com"

    try:
        admin_exists = User.query.filter_by(email=ADMIN_EMAIL).first()
    except Exception:
        # Table might not exist yet
        create_tables(db)
        admin_exists = User.query.filter_by(email=ADMIN_EMAIL).first()

    if not admin_exists:
        create_admin(
            email=ADMIN_EMAIL,
            password="adminpassword#2025",
            photo_url=DEFAULT_ADMIN_PHOTO
        )
        print(f"Default admin account created: {ADMIN_EMAIL} / adminpassword#2025")
    else:
        print(f"Admin account already exists: {ADMIN_EMAIL}")

if __name__ == '__main__':
    # Dev server — in production, use Gunicorn/uWSGI behind Nginx
    app.run(host='0.0.0.0', port=5000, debug=True)
