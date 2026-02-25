"""Notification utility functions for creating common notification types"""
from app.models.notification import Notification
from app.extensions import db, socketio
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)
PH_TZ = pytz.timezone('Asia/Manila')


class NotificationManager:
    """Manager for creating and emitting notifications"""
    
    @staticmethod
    def get_notification_config(notification_type):
        """Get default icon and color for notification type"""
        config = {
            'booking_created': {
                'icon': 'fas fa-calendar-check',
                'type': 'booking',
                'color': 'info'
            },
            'booking_confirmed': {
                'icon': 'fas fa-check-circle',
                'type': 'booking',
                'color': 'success'
            },
            'booking_rejected': {
                'icon': 'fas fa-times-circle',
                'type': 'booking',
                'color': 'danger'
            },
            'booking_cancelled': {
                'icon': 'fas fa-ban',
                'type': 'booking',
                'color': 'warning'
            },
            'booking_completed': {
                'icon': 'fas fa-check',
                'type': 'booking',
                'color': 'success'
            },
            'new_message': {
                'icon': 'fas fa-envelope',
                'type': 'message',
                'color': 'info'
            },
            'merchant_approval': {
                'icon': 'fas fa-store',
                'type': 'info',
                'color': 'success'
            },
            'merchant_rejection': {
                'icon': 'fas fa-store',
                'type': 'warning',
                'color': 'danger'
            },
            'profile_updated': {
                'icon': 'fas fa-user-circle',
                'type': 'info',
                'color': 'info'
            },
            'password_changed': {
                'icon': 'fas fa-lock',
                'type': 'info',
                'color': 'info'
            }
        }
        return config.get(notification_type, {
            'icon': 'fas fa-bell',
            'type': 'info',
            'color': 'info'
        })
    
    @staticmethod
    def create_and_emit(user_id, title, message, notification_type='info', 
                       link=None, related_id=None, related_type=None, from_user_id=None):
        """Create notification and emit via SocketIO in real-time
        
        Args:
            user_id: Recipient user ID
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            link: Link to resource
            related_id: ID of related resource
            related_type: Type of related resource
            from_user_id: User ID of sender (optional)
        """
        try:
            if not user_id:
                logger.error("[NOTIF MANAGER] ❌ user_id is required but was None or empty")
                return None
                
            print(f"\n[NOTIF MANAGER] create_and_emit called")
            print(f"  user_id: {user_id}")
            print(f"  title: {title}")
            print(f"  from_user_id: {from_user_id}")
            print(f"  notification_type: {notification_type}")
            
            config = NotificationManager.get_notification_config(notification_type)
            print(f"  config: {config}")
            
            # Create notification in database with user_id validation
            print(f"[NOTIF MANAGER] Calling Notification.create_notification()...")
            notification = Notification.create_notification(
                user_id=int(user_id),
                from_user_id=int(from_user_id) if from_user_id else None,
                title=title,
                message=message,
                notification_type=config.get('type', 'info'),
                icon=config.get('icon', 'fas fa-bell'),
                link=link,
                related_id=related_id,
                related_type=related_type
            )
            
            print(f"[NOTIF MANAGER] Notification.create_notification returned: {notification}")
            
            if notification:
                print(f"[NOTIF MANAGER] ✓ Notification created with ID {notification.id}")
                print(f"[NOTIF MANAGER] ✓ Saved to user {notification.user_id}")
                
                # Emit via SocketIO to user's room for real-time delivery
                try:
                    room = f'user_{user_id}'
                    print(f"[NOTIF MANAGER] 📡 Emitting new_notification_received to room: {room}")
                    socketio.emit('new_notification_received', {
                        'notification_id': notification.id,
                        'title': notification.title,
                        'message': notification.message,
                        'type': notification.notification_type,
                        'icon': notification.icon,
                        'link': notification.link,
                        'timestamp': datetime.now(PH_TZ).isoformat()
                    }, room=room, namespace='/')
                    print(f"[NOTIF MANAGER] ✓ SocketIO event emitted to {room}")
                except Exception as emit_error:
                    print(f"[NOTIF MANAGER] ⚠️  SocketIO emit error (notification still saved): {emit_error}")
                    logger.warning(f"SocketIO emit failed but notification was saved: {emit_error}")
                
                logger.info(f"✅ Notification {notification.id} created and emitted for user {user_id}: {title}")
                print(f"[NOTIF MANAGER] ✅ COMPLETE - Notification {notification.id} ready\n")
                return notification
            else:
                print(f"[NOTIF MANAGER] ✗ create_notification returned None")
                logger.error(f"Failed to create notification for user {user_id}")
                return None
                
        except Exception as e:
            print(f"[NOTIF MANAGER] ❌ EXCEPTION: {str(e)}")
            import traceback
            traceback.print_exc()
            logger.error(f"Error creating and emitting notification: {str(e)}", exc_info=True)
            return None
    
    @staticmethod
    def notify_booking_created(user_id, booking_number, merchant_name, appointment_date, related_booking_id=None, from_user_id=None):
        """Notify user when booking is created"""
        title = "📌 Booking Created"
        message = f"Your booking {booking_number} with {merchant_name} for {appointment_date} has been submitted. The merchant will review and confirm your booking shortly."
        return NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='booking_created',
            link=None,
            related_id=related_booking_id,
            related_type='booking',
            from_user_id=from_user_id
        )
    
    @staticmethod
    def notify_booking_confirmed(user_id, booking_number, merchant_name, related_booking_id=None, from_user_id=None):
        """Notify user when booking is confirmed"""
        title = "✅ Booking Confirmed"
        message = f"Great! Your booking {booking_number} with {merchant_name} has been confirmed. You're all set!"
        return NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='booking_confirmed',
            link=None,
            related_id=related_booking_id,
            related_type='booking',
            from_user_id=from_user_id
        )
    
    @staticmethod
    def notify_booking_rejected(user_id, booking_number, merchant_name, reason='', related_booking_id=None, from_user_id=None):
        """Notify user when booking is rejected"""
        title = "❌ Booking Not Approved"
        message = f"Unfortunately, {merchant_name} was unable to confirm your booking {booking_number}."
        if reason:
            message += f" Reason: {reason}"
        message += " Please try another date or service provider."
        return NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='booking_rejected',
            link=None,
            related_id=related_booking_id,
            related_type='booking',
            from_user_id=from_user_id
        )
    
    @staticmethod
    def notify_booking_completed(user_id, booking_number, merchant_name, related_booking_id=None, from_user_id=None):
        """Notify user when booking is completed"""
        title = "🎉 Service Completed"
        message = f"Your booking {booking_number} with {merchant_name} has been completed. Thank you for using our service!"
        return NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='booking_completed',
            link=None,
            related_id=related_booking_id,
            related_type='booking',
            from_user_id=from_user_id
        )
    
    @staticmethod
    def notify_merchant_new_booking(user_id, booking_number, customer_name, appointment_date, related_booking_id=None, from_user_id=None):
        """Notify merchant when new booking is received"""
        title = "📋 New Booking Request"
        message = f"You have a new booking from {customer_name} (#{booking_number}) for {appointment_date}. Please review and confirm or reject."
        return NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='booking_created',
            link=None,
            related_id=related_booking_id,
            related_type='booking',
            from_user_id=from_user_id
        )
    
    @staticmethod
    def notify_merchant_approval(merchant_user_id, merchant_name):
        """Notify merchant when application is approved"""
        title = "🎉 Store Approved"
        message = f"Congratulations! Your merchant application for {merchant_name} has been approved. You can now accept bookings!"
        return NotificationManager.create_and_emit(
            user_id=merchant_user_id,
            title=title,
            message=message,
            notification_type='merchant_approval',
            link=None,
            related_type='merchant'
        )
    
    @staticmethod
    def notify_merchant_rejection(merchant_user_id, merchant_name, reason=''):
        """Notify merchant when application is rejected"""
        title = "⚠️ Application Under Review"
        message = f"We're currently reviewing your merchant application for {merchant_name}."
        if reason:
            message += f" Note: {reason}"
        message += " We'll contact you soon with updates."
        return NotificationManager.create_and_emit(
            user_id=merchant_user_id,
            title=title,
            message=message,
            notification_type='merchant_rejection',
            link=None,
            related_type='merchant'
        )
    
    @staticmethod
    def notify_user_registering(user_id, first_name):
        """Notify user on successful registration"""
        title = "👋 Welcome to Petsona!"
        message = f"Welcome {first_name}! Your account has been successfully created. Start exploring pet services near you!"
        return NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='info',
            link=None,
            related_type='user'
        )
    
    @staticmethod
    def notify_password_changed(user_id):
        """Notify user when password is changed"""
        title = "🔐 Password Changed"
        message = "Your password has been successfully changed. If this wasn't you, please contact support immediately."
        return NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='password_changed',
            link=None,
            related_type='user'
        )
    
    @staticmethod
    def notify_profile_updated(user_id):
        """Notify user when profile is updated"""
        title = "✏️ Profile Updated"
        message = "Your profile has been successfully updated."
        return NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='profile_updated',
            link=None,
            related_type='user'
        )
    
    @staticmethod
    def notify_booking_no_show(user_id, booking_number, merchant_name, related_booking_id=None, from_user_id=None):
        """Notify user when booking is marked as no-show"""
        title = "⚠️ Booking Marked No-Show"
        message = f"Your booking {booking_number} with {merchant_name} has been marked as no-show. Please contact the merchant if this was a mistake."
        return NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='booking_rejected',
            link=None,
            related_id=related_booking_id,
            related_type='booking',
            from_user_id=from_user_id
        )
    
    @staticmethod
    def notify_booking_cancelled_by_customer(user_id, booking_number, customer_name, related_booking_id=None, from_user_id=None):
        """Notify merchant when customer cancels a booking"""
        title = "🚫 Booking Cancelled by Customer"
        message = f"Customer {customer_name} has cancelled booking {booking_number}. Your schedule is now available for this slot."
        return NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='booking_cancelled',
            link=None,
            related_id=related_booking_id,
            related_type='booking',
            from_user_id=from_user_id
        )
    
    @staticmethod
    def notify_new_message(user_id, sender_name):
        """Notify user when they receive a message"""
        title = "💬 New Message"
        message = f"You have a new message from {sender_name}."
        return NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='new_message',
            link=None,
            related_type='message'
        )
