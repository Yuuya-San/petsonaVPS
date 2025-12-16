from flask import request
from flask_login import current_user
from datetime import datetime
from ..models import AuditLog, db
import json

def log_event(event: str, details: dict = None):
    log = AuditLog(
        event=event,
        actor_id=current_user.id if current_user.is_authenticated else None,
        actor_email=current_user.email if current_user.is_authenticated else None,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent'),
        timestamp=datetime.utcnow()
    )

    if details:
        log.set_details(details)

    db.session.add(log)
    db.session.commit()
