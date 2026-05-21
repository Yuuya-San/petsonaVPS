from datetime import datetime
import json
from app.extensions import db
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    event = db.Column(db.String(128), nullable=False)
    actor_id = db.Column(db.Integer)
    actor_email = db.Column(db.String(255))
    ip_address = db.Column(db.String(100))
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=get_ph_datetime, index=True)
    details = db.Column(db.Text)
    deleted_at = db.Column(db.DateTime)

    def set_details(self, data: dict):
        self.details = json.dumps(data) if data else None

    def get_details(self) -> dict:
        try:
            return json.loads(self.details) if self.details else {}
        except Exception:
            return {}
    
    @property
    def timestamp_ph(self):
        """Get timestamp converted to Philippine timezone for display"""
        if not self.timestamp:
            return None
        tz_aware = self.timestamp.replace(tzinfo=pytz.UTC) if self.timestamp.tzinfo is None else self.timestamp
        return tz_aware.astimezone(PH_TZ)
    
    @property
    def deleted_at_ph(self):
        """Get deleted_at converted to Philippine timezone for display"""
        if not self.deleted_at:
            return None
        tz_aware = self.deleted_at.replace(tzinfo=pytz.UTC) if self.deleted_at.tzinfo is None else self.deleted_at
        return tz_aware.astimezone(PH_TZ)
