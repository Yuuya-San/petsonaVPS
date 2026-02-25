"""API endpoints for notification management"""
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from app.extensions import db, csrf
from app.models import Notification
import logging

logger = logging.getLogger(__name__)

notifications_bp = Blueprint('notifications', __name__, url_prefix='/api/notifications')


@csrf.exempt
@notifications_bp.route('/<int:notification_id>', methods=['DELETE'])
@login_required
def delete_notification(notification_id):
    """Delete a single notification for the current user"""
    try:
        # Get the notification and ensure it belongs to the current user
        notification = Notification.query.filter_by(
            id=notification_id,
            user_id=current_user.id
        ).first_or_404()
        
        # Delete the notification
        db.session.delete(notification)
        db.session.commit()
        
        logger.info(f"✅ Notification {notification_id} deleted for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Notification deleted successfully',
            'notification_id': notification_id
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error deleting notification: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to delete notification',
            'error': str(e)
        }), 500


@csrf.exempt
@notifications_bp.route('/delete-all', methods=['DELETE'])
@login_required
def delete_all_notifications():
    """Delete all notifications for the current user"""
    try:
        # Get count of notifications to be deleted
        count = Notification.query.filter_by(user_id=current_user.id).count()
        
        # Delete all notifications for the current user
        Notification.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        
        logger.info(f"✅ {count} notifications deleted for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': f'{count} notifications deleted successfully',
            'deleted_count': count
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error deleting all notifications: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to delete notifications',
            'error': str(e)
        }), 500


@csrf.exempt
@notifications_bp.route('/<int:notification_id>/read', methods=['PATCH'])
@login_required
def mark_notification_read(notification_id):
    """Mark a single notification as read"""
    try:
        # Get the notification and ensure it belongs to the current user
        notification = Notification.query.filter_by(
            id=notification_id,
            user_id=current_user.id
        ).first_or_404()
        
        # Mark as read
        if not notification.is_read:
            notification.is_read = True
            from datetime import datetime
            import pytz
            PH_TZ = pytz.timezone('Asia/Manila')
            notification.read_at = datetime.now(PH_TZ)
            db.session.commit()
            
            logger.info(f"✅ Notification {notification_id} marked as read for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Notification marked as read',
            'notification_id': notification_id,
            'is_read': True,
            'read_at': notification.read_at.isoformat() if notification.read_at else None
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error marking notification as read: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to mark notification as read',
            'error': str(e)
        }), 500
