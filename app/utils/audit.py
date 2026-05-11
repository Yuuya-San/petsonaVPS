from flask import request
from flask_login import current_user # pyright: ignore[reportMissingImports]
from datetime import datetime
from app.models import *
import json
from app.extensions import db
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)

def log_event(event: str, details: dict = None, commit: bool = False):
    """
    Log an audit event to the database.
    
    Args:
        event: The event type/name
        details: Optional dict of event details
        commit: Whether to commit immediately (default: False to prevent slowness)
    """
    try:
        log = AuditLog(
            event=event,
            actor_id=current_user.id if current_user.is_authenticated else None,
            actor_email=current_user.email if current_user.is_authenticated else None,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            timestamp=get_ph_datetime()
        )

        if details:
            log.set_details(details)

        db.session.add(log)
        
        if commit:
            db.session.commit()
    except Exception as e:
        import logging
        logging.warning(f"Failed to log event '{event}': {str(e)}")
        db.session.rollback()

def user_snapshot(user):
    """Return all User fields as a dict for audit logging."""
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "photo_url": user.photo_url,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "failed_login_attempts": user.failed_login_attempts,
        "lockout_until": user.lockout_until.isoformat() if user.lockout_until else None,
        "totp_secret": user.totp_secret,
        "is_2fa_enabled": user.is_2fa_enabled
    }
