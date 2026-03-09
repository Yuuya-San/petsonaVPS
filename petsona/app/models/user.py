from datetime import datetime
from flask_login import UserMixin # pyright: ignore[reportMissingImports]
from typing import Optional
from app.extensions import db, bcrypt
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_now():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)


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
    last_seen = db.Column(db.DateTime, default=get_ph_now)

    failed_login_attempts = db.Column(db.Integer, default=0)
    lockout_until = db.Column(db.DateTime)

    role = db.Column(db.String(32), default="user", index=True)

    totp_secret = db.Column(db.String(32))
    is_2fa_enabled = db.Column(db.Boolean, default=False)
    
    registration_method = db.Column(db.String(32), default='system')  # 'system' or 'google'
    session_token = db.Column(db.String(255))

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

    def get_online_status(self, is_online: bool = False) -> dict:
        """Get user online status and last seen time"""
        if is_online:
            return {
                'status': 'online',
                'display_text': 'Active now',
                'timestamp': self.last_seen.isoformat() if self.last_seen else None,
                'is_online': True
            }
        
        # Calculate time difference
        if self.last_seen:
            now_ph = datetime.now(PH_TZ)
            last_seen_ph = self.last_seen.replace(tzinfo=pytz.UTC).astimezone(PH_TZ)
            delta_seconds = (now_ph - last_seen_ph).total_seconds()
            
            # Format based on time difference
            if delta_seconds < 60:
                display_text = 'Just now'
            elif delta_seconds < 3600:
                minutes = int(delta_seconds // 60)
                display_text = f'{minutes}m ago' if minutes > 1 else '1m ago'
            elif delta_seconds < 86400:
                hours = int(delta_seconds // 3600)
                display_text = f'{hours}h ago' if hours > 1 else '1h ago'
            else:
                days = int(delta_seconds // 86400)
                display_text = f'{days}d ago' if days > 1 else '1d ago'
            
            return {
                'status': 'offline',
                'display_text': display_text,
                'timestamp': self.last_seen.isoformat(),
                'is_online': False
            }
        
        return {
            'status': 'offline',
            'display_text': 'Offline',
            'timestamp': None,
            'is_online': False
        }

    def update_last_seen(self):
        """Update user's last seen timestamp using Philippine timezone"""
        self.last_seen = datetime.now(PH_TZ)
        db.session.commit()


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
