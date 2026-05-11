from datetime import datetime
from app.extensions import db
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_now():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)

def get_utc_now():
    """Get current UTC datetime (naive for database storage)"""
    return datetime.utcnow()


class PasswordResetToken(db.Model):
    """Track password reset tokens for one-time use enforcement"""
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    token_hash = db.Column(db.String(255), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=get_utc_now)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)  # NULL if not used yet
    is_used = db.Column(db.Boolean, default=False, index=True)

    def __repr__(self):
        return f'<PasswordResetToken user_id={self.user_id} is_used={self.is_used}>'

    @classmethod
    def create_token(cls, user_id, token_hash, expiry_seconds=1800):
        """Create a new password reset token (30 mins default)"""
        expires_at = get_utc_now()
        expires_at = expires_at.replace(microsecond=0) + \
                    __import__('datetime').timedelta(seconds=expiry_seconds)
        
        token = cls(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        db.session.add(token)
        db.session.commit()
        return token

    @classmethod
    def get_valid_token(cls, token_hash):
        """Get token if it exists, is not used, and not expired"""
        token = cls.query.filter_by(token_hash=token_hash).first()
        
        if not token:
            return None
        
        if token.is_used:
            return None  # Already used
        
        if get_utc_now() > token.expires_at:
            return None  # Expired
        
        return token

    def mark_as_used(self):
        """Mark token as used"""
        self.is_used = True
        self.used_at = get_utc_now()
        db.session.commit()

    @classmethod
    def check_token_status(cls, token_hash):
        """Check why a token is invalid: 'not_found', 'expired', 'already_used', or None if valid"""
        token = cls.query.filter_by(token_hash=token_hash).first()
        
        if not token:
            return 'not_found'
        
        if token.is_used:
            return 'already_used'
        
        if get_utc_now() > token.expires_at:
            return 'expired'
        
        return None  # Token is valid
