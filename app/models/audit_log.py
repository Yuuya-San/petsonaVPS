from datetime import datetime
import json
from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    event = db.Column(db.String(128), nullable=False)
    actor_id = db.Column(db.Integer)
    actor_email = db.Column(db.String(255))
    ip_address = db.Column(db.String(100))
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    details = db.Column(db.Text)
    deleted_at = db.Column(db.DateTime)

    def set_details(self, data: dict):
        self.details = json.dumps(data) if data else None

    def get_details(self) -> dict:
        try:
            return json.loads(self.details) if self.details else {}
        except Exception:
            return {}
