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

    try:
        admin_exists = User.query.filter_by(role='admin').first()
    except Exception as e:
        # Table might not exist yet
        create_tables(db)
        admin_exists = User.query.filter_by(role='admin').first()

    if not admin_exists:
        # Create admin with default photo
        create_admin(
            email="jeysalas05@gmail.com",
            password="adminpassword#2025",
            photo_url=DEFAULT_ADMIN_PHOTO
        )
        print("Default admin account created: jeysalas05@gmail.com / adminpassword#2025")

if __name__ == '__main__':
    # Dev server — in production, use Gunicorn/uWSGI behind Nginx
    app.run(host='0.0.0.0', port=5000, debug=True)
