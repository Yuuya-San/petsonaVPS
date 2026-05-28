from datetime import datetime, timedelta
from flask_login import UserMixin # pyright: ignore[reportMissingImports]
from typing import Optional
from app.extensions import db, bcrypt
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_now():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)

def get_utc_now():
    """Get current UTC datetime for database storage"""
    return datetime.utcnow()


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    photo_url = db.Column(db.String(255))
    password_hash = db.Column(db.String(128), nullable=False)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_utc_now)
    deleted_at = db.Column(db.DateTime)
    last_seen = db.Column(db.DateTime, default=get_utc_now)

    failed_login_attempts = db.Column(db.Integer, default=0)
    lockout_until = db.Column(db.DateTime)

    role = db.Column(db.String(32), default="user", index=True)
    subscription_plan = db.Column(db.String(32), default='basic', nullable=False, index=True)
    subscription_status = db.Column(db.String(32), default='active', nullable=False)
    subscription_renewal_date = db.Column(db.DateTime, nullable=True)
    pending_subscription_plan = db.Column(db.String(32), nullable=True)
    subscription_payment_due = db.Column(db.DateTime, nullable=True)
    
    # PayMongo payment tracking
    paymongo_payment_id = db.Column(db.String(255), nullable=True, unique=True, index=True)
    paymongo_intent_id = db.Column(db.String(255), nullable=True, unique=True, index=True)
    paymongo_payment_status = db.Column(db.String(32), nullable=True)
    paymongo_last_payment_update = db.Column(db.DateTime, nullable=True)
    paymongo_payment_method = db.Column(db.String(32), nullable=True)  # 'card', 'ewallet', 'dob', etc.
    
    quiz_access_count = db.Column(db.Integer, default=0, nullable=False)

    totp_secret = db.Column(db.String(32))
    is_2fa_enabled = db.Column(db.Boolean, default=False)
    
    registration_method = db.Column(db.String(32), default='system')  # 'system' or 'google'
    session_token = db.Column(db.String(255))
    
    has_temp_password = db.Column(db.Boolean, default=False)  # True if password was set by admin

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_user(self):
        return self.role == "user"

    @property
    def is_merchant(self):
        return self.role == "merchant"

    @property
    def plan(self):
        return (self.subscription_plan or 'basic').lower()

    @property
    def is_basic_plan(self):
        return self.plan == 'basic'

    @property
    def is_premium_plan(self):
        return self.plan == 'premium'

    @property
    def is_pro_plan(self):
        return self.plan == 'pro'

    @property
    def has_premium_access(self):
        return self.is_admin or self.is_premium_plan or self.is_pro_plan

    @property
    def can_access_breed_specific(self):
        return self.is_admin or self.has_premium_access

    @property
    def can_edit_store(self):
        return self.is_admin or self.has_premium_access

    @property
    def has_available_quiz_slot(self):
        return self.is_admin or self.has_premium_access or (self.quiz_access_count or 0) < 1

    @property
    def is_pending_subscription(self):
        return self.subscription_status == 'pending' and bool(self.pending_subscription_plan)

    def increment_quiz_access(self):
        self.quiz_access_count = (self.quiz_access_count or 0) + 1

    def set_subscription(self, plan: str, renewal_date=None):
        self.subscription_plan = plan or 'basic'
        self.subscription_status = 'active'
        self.subscription_renewal_date = renewal_date
        self.pending_subscription_plan = None
        self.subscription_payment_due = None
        # Clear PayMongo payment tracking
        self.paymongo_payment_status = None
        self.paymongo_last_payment_update = None

    def set_free_basic(self):
        self.set_subscription('basic', None)

    def set_premium(self, renewal_date):
        self.set_subscription('premium', renewal_date)

    def set_pro(self, renewal_date):
        self.set_subscription('pro', renewal_date)

    def set_pending_subscription(self, plan: str, payment_due):
        self.subscription_status = 'pending'
        self.pending_subscription_plan = plan
        self.subscription_payment_due = payment_due

    def activate_pending_subscription(self):
        if not self.pending_subscription_plan:
            return

        plan = self.pending_subscription_plan.lower()
        if plan == 'premium':
            renewal_date = get_ph_now() + timedelta(days=30)
        elif plan == 'pro':
            renewal_date = get_ph_now() + timedelta(days=365)
        else:
            renewal_date = None

        self.subscription_plan = plan
        self.subscription_status = 'active'
        self.subscription_renewal_date = renewal_date
        self.pending_subscription_plan = None
        self.subscription_payment_due = None

    def cancel_subscription(self):
        self.set_free_basic()
        self.subscription_status = 'active'
        self.pending_subscription_plan = None
        self.subscription_payment_due = None

    def set_paymongo_payment(self, payment_id: str, intent_id: str, payment_method: str = None):
        """Set PayMongo payment tracking details"""
        self.paymongo_payment_id = payment_id
        self.paymongo_intent_id = intent_id
        self.paymongo_payment_method = payment_method or 'card'
        self.paymongo_last_payment_update = get_utc_now()

    def update_paymongo_status(self, status: str):
        """Update PayMongo payment status"""
        self.paymongo_payment_status = status
        self.paymongo_last_payment_update = get_utc_now()

    def clear_paymongo_payment(self):
        """Clear PayMongo payment tracking"""
        self.paymongo_payment_id = None
        self.paymongo_intent_id = None
        self.paymongo_payment_status = None
        self.paymongo_payment_method = None
        self.paymongo_last_payment_update = None

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
    
    @property
    def created_at_ph(self):
        """Get created_at converted to Philippine timezone for display"""
        if not self.created_at:
            return None
        tz_aware = self.created_at.replace(tzinfo=pytz.UTC) if self.created_at.tzinfo is None else self.created_at
        return tz_aware.astimezone(PH_TZ)
    
    @property
    def deleted_at_ph(self):
        """Get deleted_at converted to Philippine timezone for display"""
        if not self.deleted_at:
            return None
        tz_aware = self.deleted_at.replace(tzinfo=pytz.UTC) if self.deleted_at.tzinfo is None else self.deleted_at
        return tz_aware.astimezone(PH_TZ)
    
    @property
    def last_seen_ph(self):
        """Get last_seen converted to Philippine timezone for display"""
        if not self.last_seen:
            return None
        tz_aware = self.last_seen.replace(tzinfo=pytz.UTC) if self.last_seen.tzinfo is None else self.last_seen
        return tz_aware.astimezone(PH_TZ)
    
    @property
    def lockout_until_ph(self):
        """Get lockout_until converted to Philippine timezone for display"""
        if not self.lockout_until:
            return None
        tz_aware = self.lockout_until.replace(tzinfo=pytz.UTC) if self.lockout_until.tzinfo is None else self.lockout_until
        return tz_aware.astimezone(PH_TZ)

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
