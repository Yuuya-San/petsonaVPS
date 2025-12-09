
from app import create_app
from app.models import User, create_admin, db

# Create Flask app
app = create_app()

# Auto-create default admin account if none exists
with app.app_context():
    if not User.query.filter_by(role='admin').first():
        create_admin("jeysalas05@gmail.com", "adminpassword#2025")
        print("Default admin account created: jeysalas05@gmail.com / adminpassword#2025")

if __name__ == '__main__':
    # Dev server — in production, use Gunicorn/uWSGI behind Nginx
    app.run(host='0.0.0.0', port=5000, debug=True)
