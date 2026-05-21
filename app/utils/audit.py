"""
Comprehensive audit logging system for Petsona VPS.

This module provides utilities to log all user and system actions to the audit_logs table.
Every route action that modifies data or performs sensitive operations must be logged.

Event Naming Convention:
- entity.action (e.g., user.login, species.created, booking.confirmed)
- For list actions: entity.list_viewed
- For sensitive operations: entity.action_type (e.g., user.password_changed)

Actor: The user or system that performed the action
Details: Relevant metadata about the action (old values, new values, affected entities, etc.)
"""

from flask import request
from flask_login import current_user # pyright: ignore[reportMissingImports]
from datetime import datetime
from functools import wraps
import logging
import json
from app.models import *
from app.extensions import db
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')
logger = logging.getLogger(__name__)


def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)


def log_event(event: str, details: dict = None, commit: bool = True, actor_id: int = None, actor_email: str = None):
    """
    Log an audit event to the database.
    
    Comprehensive audit logging for all system and user actions.
    
    Args:
        event (str): Event type/name following convention: entity.action (e.g., 'user.login', 'species.created')
        details (dict, optional): Event metadata including old_values, new_values, affected_entity_ids, reason, etc.
        commit (bool, optional): Whether to commit immediately. Defaults to True to ensure audit logs are always persisted.
        actor_id (int, optional): User ID of actor. If None, uses current_user.id if authenticated.
        actor_email (str, optional): Email of actor. If None, uses current_user.email if authenticated.
    
    Returns:
        AuditLog: The created audit log entry, or None if logging failed
    
    Example:
        # User login event
        log_event('user.login', {'ip_address': '192.168.1.1'})
        
        # Breed creation with changes
        log_event('breed.created', {
            'breed_id': 123,
            'name': 'Golden Retriever',
            'species_id': 5
        })
        
        # Update with old/new values
        log_event('user.updated', {
            'user_id': 45,
            'changes': {
                'first_name': {'old': 'John', 'new': 'Jonathan'},
                'last_name': {'old': 'Doe', 'new': 'Smith'}
            }
        })
    """
    try:
        # Determine actor
        final_actor_id = actor_id if actor_id is not None else (current_user.id if current_user.is_authenticated else None)
        final_actor_email = actor_email if actor_email is not None else (current_user.email if current_user.is_authenticated else None)
        
        # Create audit log entry
        log = AuditLog(
            event=event,
            actor_id=final_actor_id,
            actor_email=final_actor_email,
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent') if request else None,
            timestamp=get_ph_datetime()
        )

        if details:
            log.set_details(details)

        db.session.add(log)
        
        if commit:
            db.session.commit()
        
        logger.debug(f"✓ Audit event logged: {event} by {final_actor_email or 'anonymous'}")
        return log
        
    except Exception as e:
        logger.error(f"✗ Failed to log event '{event}': {str(e)}", exc_info=True)
        try:
            db.session.rollback()
        except:
            pass
        return None


def audit_action(event_name: str):
    """
    Decorator to automatically log route actions with detailed context.
    
    Captures route execution, actor information, request details, and changes.
    
    Args:
        event_name (str): Event identifier (e.g., 'user.created', 'breed.updated')
    
    Usage:
        @bp.route('/user/create', methods=['POST'])
        @audit_action('user.created')
        @login_required
        def create_user():
            # Your route logic here
            return render_template('user_created.html')
    
    Example with details function:
        def get_details():
            return {
                'user_email': current_user.email,
                'action_type': 'manual_creation'
            }
        
        @audit_action('user.created')
        def create_user():
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Execute the route function
                result = func(*args, **kwargs)
                
                # Log successful action
                details = {
                    'endpoint': request.endpoint,
                    'method': request.method,
                    'url_path': request.path
                }
                log_event(event_name, details=details)
                
                return result
            except Exception as e:
                # Log failed action
                log_event(
                    f"{event_name}_failed",
                    details={'error': str(e), 'endpoint': request.endpoint},
                    commit=True
                )
                raise
        
        return wrapper
    return decorator


def user_snapshot(user):
    """
    Return complete User object snapshot for audit logging.
    
    Captures all critical user fields for historical record-keeping.
    Used when logging user modifications to maintain a complete audit trail.
    
    Args:
        user: User model instance
    
    Returns:
        dict: Complete user data snapshot
    """
    if not user:
        return None
        
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
        "totp_secret": bool(user.totp_secret),  # Never log actual secret
        "is_2fa_enabled": user.is_2fa_enabled
    }


def log_action_with_changes(event_name: str, entity_id: int, old_values: dict = None, new_values: dict = None, 
                            entity_type: str = None, metadata: dict = None):
    """
    Log an entity modification action with before/after values.
    
    Comprehensive change tracking for audit trail. Captures what changed, who changed it, and when.
    
    Args:
        event_name (str): Event type (e.g., 'breed.updated', 'user.edited')
        entity_id (int): ID of the modified entity
        old_values (dict, optional): Previous values of modified fields
        new_values (dict, optional): New values of modified fields
        entity_type (str, optional): Type of entity (e.g., 'breed', 'user', 'species')
        metadata (dict, optional): Additional context (reason, source, etc.)
    
    Example:
        log_action_with_changes(
            'user.updated',
            entity_id=123,
            old_values={'email': 'old@example.com'},
            new_values={'email': 'new@example.com'},
            entity_type='user'
        )
    """
    details = {
        'entity_id': entity_id,
        'entity_type': entity_type,
    }
    
    if old_values or new_values:
        details['changes'] = {}
        if old_values:
            details['changes']['old'] = old_values
        if new_values:
            details['changes']['new'] = new_values
    
    if metadata:
        details['metadata'] = metadata
    
    return log_event(event_name, details=details)


def log_list_view(entity_type: str, filters: dict = None):
    """
    Log when users view entity lists/dashboards.
    
    Tracks user navigation and data access for security and analytics.
    
    Args:
        entity_type (str): Type of entity being viewed (e.g., 'users', 'species', 'breeds')
        filters (dict, optional): Active filters/search parameters
    
    Example:
        log_list_view('species', {'role': 'admin'})
    """
    details = {'entity_type': entity_type}
    if filters:
        details['filters'] = filters
    
    return log_event(f'{entity_type}.list_viewed', details=details)


def log_data_access(resource_type: str, resource_id: int, access_type: str = 'view'):
    """
    Log when users access sensitive data or resources.
    
    Args:
        resource_type (str): Type of resource (e.g., 'user_profile', 'booking', 'message')
        resource_id (int): Resource ID
        access_type (str): Type of access ('view', 'download', 'export')
    """
    return log_event(
        f'{resource_type}.{access_type}',
        details={'resource_id': resource_id}
    )


def log_error_action(action_type: str, reason: str, affected_entity: dict = None):
    """
    Log failed or unauthorized actions.
    
    Security logging for failed attempts, permission violations, and errors.
    
    Args:
        action_type (str): Type of action that failed
        reason (str): Reason for failure/error
        affected_entity (dict, optional): Entity that the action targeted
    """
    details = {'reason': reason}
    if affected_entity:
        details['affected_entity'] = affected_entity
    
    return log_event(f'{action_type}_denied', details=details)
