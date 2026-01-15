from datetime import datetime
from flask_login import UserMixin # pyright: ignore[reportMissingImports]
from typing import Optional
from app.extensions import db, bcrypt


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    photo_url = db.Column(db.String(255))
    password_hash = db.Column(db.String(128), nullable=False)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)

    failed_login_attempts = db.Column(db.Integer, default=0)
    lockout_until = db.Column(db.DateTime)

    role = db.Column(db.String(32), default="user", index=True)

    totp_secret = db.Column(db.String(32))
    is_2fa_enabled = db.Column(db.Boolean, default=False)


    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_user(self):
        return self.role == "user"

    @property
    def is_merchant(self):
        return self.role == "merchant"

    def set_password(self, password: str):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)


def create_admin(email: str, password: str, photo_url: Optional[str] = None):
    try:
        admin = User(
            email=email.lower(),
            first_name="Petsona",
            last_name="Support",
            role="admin",
            photo_url=photo_url
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        return admin
    except Exception:
        db.session.rollback()
        return None
