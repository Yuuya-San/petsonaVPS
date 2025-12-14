# Utility function to create an admin user (call from shell or script)
def create_admin(email: str, password: str, photo_url: str = None):
    """Create an admin user directly in the database with optional photo."""
    admin = User(
        email=email.lower(),
        role='admin',
        photo_url=photo_url  # set default avatar if provided
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    return admin

"""Database models for the app: User and AuditLog.
AuditLog is used for storing an immutable (append-only) log of important events.
"""
from .extensions import db, bcrypt
from flask_login import UserMixin
from datetime import datetime
import json

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(64), nullable=True)      
    last_name = db.Column(db.String(64), nullable=True)       
    photo_url = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Lockout support
    failed_login_attempts = db.Column(db.Integer, default=0)
    lockout_until = db.Column(db.DateTime, nullable=True)

    # Role-based access
    role = db.Column(db.String(32), default='user', nullable=False, index=True)  # 'user' or 'admin'

    # 2FA support
    totp_secret = db.Column(db.String(32), nullable=True)
    is_2fa_enabled = db.Column(db.Boolean, default=False)

    def set_password(self, password: str):
        """Hashes the password and stores it."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password: str) -> bool:
        """Verifies the password."""
        return bcrypt.check_password_hash(self.password_hash, password)

class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    event = db.Column(db.String(128), nullable=False)          # e.g. 'user.login_success'
    actor_id = db.Column(db.Integer, nullable=True)            # user id if applicable
    actor_email = db.Column(db.String(255), nullable=True)     # email if applicable
    ip_address = db.Column(db.String(100), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    details = db.Column(db.Text, nullable=True)                # JSON blob for extra context

    # --- NEW METHOD ---
    def set_details(self, data: dict):
        """Store extra information as JSON string."""
        try:
            self.details = json.dumps(data)
        except Exception:
            self.details = None

    def get_details(self) -> dict:
        """Retrieve extra information as dictionary."""
        if not self.details:
            return {}
        try:
            return json.loads(self.details)
        except Exception:
            return {}

    # ---------- BACKWARD COMPATIBILITY ----------
    def set_metadata(self, data: dict):
        """Alias for old code still using set_metadata()."""
        return self.set_details(data)

    def get_metadata(self) -> dict:
        """Alias for old code using get_metadata()."""
        return self.get_details()

