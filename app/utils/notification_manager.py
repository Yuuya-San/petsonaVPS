"""Notification utility functions for creating common notification types"""
from app.models.notification import Notification
from app.extensions import db, socketio
from app.models.user import User
from flask import render_template, current_app
from app.auth.emails import send_email
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)
PH_TZ = pytz.timezone('Asia/Manila')


class NotificationManager:
    """Manager for creating and emitting notifications"""
    
    @staticmethod
    def get_frontend_url(path=''):
        """Get environment-aware frontend URL
        
        Args:
            path: Optional path to append to base URL (e.g., '/bookings', '/merchant/dashboard')
        
        Returns:
            Full URL with frontend base from config
        """
        try:
            base_url = current_app.config.get('FRONTEND_URL', 'https://petsona.online')
            if path:
                # Ensure path starts with /
                if not path.startswith('/'):
                    path = '/' + path
                return f"{base_url.rstrip('/')}{path}"
            return base_url
        except Exception as e:
            logger.warning(f"Failed to get frontend URL: {e}. Using default.")
            return f"https://petsona.online{path}" if path else "https://petsona.online"
    
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
            },
            'account_locked': {
                'icon': 'fas fa-lock-slash',
                'type': 'warning',
                'color': 'danger'
            },
            '2fa_enabled': {
                'icon': 'fas fa-shield-alt',
                'type': 'info',
                'color': 'success'
            },
            '2fa_disabled': {
                'icon': 'fas fa-shield-alt',
                'type': 'info',
                'color': 'warning'
            },
            '2fa_reset': {
                'icon': 'fas fa-shield-alt',
                'type': 'warning',
                'color': 'danger'
            },
            'security_alert': {
                'icon': 'fas fa-exclamation-triangle',
                'type': 'danger',
                'color': 'danger'
            },
            'review_received': {
                'icon': 'fas fa-star',
                'type': 'info',
                'color': 'success'
            },
            'review_responded': {
                'icon': 'fas fa-reply',
                'type': 'info',
                'color': 'info'
            },
            'pet_match_found': {
                'icon': 'fas fa-heart',
                'type': 'info',
                'color': 'info'
            },
            'suspicious_activity': {
                'icon': 'fas fa-exclamation-circle',
                'type': 'warning',
                'color': 'danger'
            },
            'unusual_login': {
                'icon': 'fas fa-sign-in-alt',
                'type': 'warning',
                'color': 'warning'
            },
            'email_changed': {
                'icon': 'fas fa-envelope',
                'type': 'info',
                'color': 'warning'
            },
            'role_changed': {
                'icon': 'fas fa-user-tag',
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
    def send_notification_email(user_id, subject, greeting, message, badge_type='info', 
                                badge_text='Notification', cta_link=None, cta_text=None, 
                                additional_info=None, is_security_alert=False):
        """Send email notification to user
        
        Args:
            user_id: Recipient user ID
            subject: Email subject
            greeting: Greeting message (e.g., "Hi John,"). Supports {{first_name}} and {{last_name}} placeholders
            message: Main notification message
            badge_type: Type of badge (info, success, warning, danger)
            badge_text: Text shown in badge
            cta_link: Call-to-action link
            cta_text: Call-to-action button text
            additional_info: Additional information box content
            is_security_alert: Whether to show security alert disclaimer
        """
        try:
            user = User.query.get(user_id)
            if not user:
                logger.warning(f"[EMAIL NOTIF] ⚠️ User {user_id} not found for email notification")
                return False
            
            # Replace template placeholders in greeting with actual user data
            processed_greeting = greeting
            if '{{first_name}}' in processed_greeting:
                processed_greeting = processed_greeting.replace('{{first_name}}', user.first_name or 'there')
            if '{{last_name}}' in processed_greeting:
                processed_greeting = processed_greeting.replace('{{last_name}}', user.last_name or '')
            
            timestamp = datetime.now(PH_TZ).strftime('%B %d, %Y at %I:%M %p')
            
            html = render_template(
                'emails/notification_email.html',
                subject=subject,
                greeting=processed_greeting,
                message=message,
                badge_type=badge_type,
                badge_text=badge_text,
                cta_link=cta_link,
                cta_text=cta_text,
                additional_info=additional_info,
                is_security_alert=is_security_alert,
                timestamp=timestamp
            )
            
            send_email(subject, [user.email], html)
            logger.info(f"✅ Email notification sent to {user.email}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"[EMAIL NOTIF] ❌ Failed to send email for user {user_id}: {str(e)}", exc_info=True)
            return False
    
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
            },
            'account_locked': {
                'icon': 'fas fa-lock-slash',
                'type': 'warning',
                'color': 'danger'
            },
            '2fa_enabled': {
                'icon': 'fas fa-shield-alt',
                'type': 'info',
                'color': 'success'
            },
            '2fa_disabled': {
                'icon': 'fas fa-shield-alt',
                'type': 'info',
                'color': 'warning'
            },
            '2fa_reset': {
                'icon': 'fas fa-shield-alt',
                'type': 'warning',
                'color': 'danger'
            },
            'security_alert': {
                'icon': 'fas fa-exclamation-triangle',
                'type': 'danger',
                'color': 'danger'
            },
            'review_received': {
                'icon': 'fas fa-star',
                'type': 'info',
                'color': 'success'
            },
            'review_responded': {
                'icon': 'fas fa-reply',
                'type': 'info',
                'color': 'info'
            },
            'pet_match_found': {
                'icon': 'fas fa-heart',
                'type': 'info',
                'color': 'info'
            },
            'suspicious_activity': {
                'icon': 'fas fa-exclamation-circle',
                'type': 'warning',
                'color': 'danger'
            },
            'unusual_login': {
                'icon': 'fas fa-sign-in-alt',
                'type': 'warning',
                'color': 'warning'
            },
            'email_changed': {
                'icon': 'fas fa-envelope',
                'type': 'info',
                'color': 'warning'
            },
            'role_changed': {
                'icon': 'fas fa-user-tag',
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
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='booking_created',
            link=None,
            related_id=related_booking_id,
            related_type='booking',
            from_user_id=from_user_id
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="Booking Created - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='info',
            badge_text='New Booking',
            cta_text="View Booking",
            cta_link=NotificationManager.get_frontend_url('/bookings')
        )
        return notif
    
    @staticmethod
    def notify_booking_confirmed(user_id, booking_number, merchant_name, related_booking_id=None, from_user_id=None):
        """Notify user when booking is confirmed"""
        title = "✅ Booking Confirmed"
        message = f"Great! Your booking {booking_number} with {merchant_name} has been confirmed. You're all set!"
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='booking_confirmed',
            link=None,
            related_id=related_booking_id,
            related_type='booking',
            from_user_id=from_user_id
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="Booking Confirmed - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='success',
            badge_text='Booking Confirmed',
            cta_text="View Booking",
            cta_link=NotificationManager.get_frontend_url('/bookings')
        )
        return notif
    
    @staticmethod
    def notify_booking_rejected(user_id, booking_number, merchant_name, reason='', related_booking_id=None, from_user_id=None):
        """Notify user when booking is rejected"""
        title = "❌ Booking Not Approved"
        message = f"Unfortunately, {merchant_name} was unable to confirm your booking {booking_number}."
        if reason:
            message += f" Reason: {reason}"
        message += " Please try another date or service provider."
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='booking_rejected',
            link=None,
            related_id=related_booking_id,
            related_type='booking',
            from_user_id=from_user_id
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="Booking Not Approved - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='danger',
            badge_text='Not Approved',
            additional_info="We recommend trying another date or exploring other service providers."
        )
        return notif
    
    @staticmethod
    def notify_booking_completed(user_id, booking_number, merchant_name, related_booking_id=None, from_user_id=None):
        """Notify user when booking is completed"""
        title = "🎉 Service Completed"
        message = f"Your booking {booking_number} with {merchant_name} has been completed. Thank you for using our service!"
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='booking_completed',
            link=None,
            related_id=related_booking_id,
            related_type='booking',
            from_user_id=from_user_id
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="Service Completed - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='success',
            badge_text='Completed',
            cta_text="Leave a Review",
            cta_link=NotificationManager.get_frontend_url('/bookings')
        )
        return notif
    
    @staticmethod
    def notify_merchant_new_booking(user_id, booking_number, customer_name, appointment_date, related_booking_id=None, from_user_id=None):
        """Notify merchant when new booking is received"""
        title = "📋 New Booking Request"
        message = f"You have a new booking from {customer_name} (#{booking_number}) for {appointment_date}. Please review and confirm or reject."
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='booking_created',
            link=None,
            related_id=related_booking_id,
            related_type='booking',
            from_user_id=from_user_id
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="New Booking Request - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='info',
            badge_text='New Booking',
            cta_text="Review Booking",
            cta_link=NotificationManager.get_frontend_url('/merchant/bookings')
        )
        return notif
    
    @staticmethod
    def notify_merchant_approval(merchant_user_id, merchant_name):
        """Notify merchant when application is approved"""
        title = "🎉 Store Approved"
        message = f"Congratulations! Your merchant application for {merchant_name} has been approved. You can now accept bookings!"
        notif = NotificationManager.create_and_emit(
            user_id=merchant_user_id,
            title=title,
            message=message,
            notification_type='merchant_approval',
            link=None,
            related_type='merchant'
        )
        NotificationManager.send_notification_email(
            user_id=merchant_user_id,
            subject="Store Approved - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='success',
            badge_text='Approved',
            cta_text="View Your Store",
            cta_link=NotificationManager.get_frontend_url('/merchant/dashboard')
        )
        return notif
    
    @staticmethod
    def notify_merchant_rejection(merchant_user_id, merchant_name, reason=''):
        """Notify merchant when application is rejected"""
        title = "⚠️ Application Under Review"
        message = f"We're currently reviewing your merchant application for {merchant_name}."
        if reason:
            message += f" Note: {reason}"
        message += " We'll contact you soon with updates."
        notif = NotificationManager.create_and_emit(
            user_id=merchant_user_id,
            title=title,
            message=message,
            notification_type='merchant_rejection',
            link=None,
            related_type='merchant'
        )
        NotificationManager.send_notification_email(
            user_id=merchant_user_id,
            subject="Application Under Review - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='warning',
            badge_text='Under Review',
            additional_info="Our team will contact you shortly with more information."
        )
        return notif
    
    @staticmethod
    def notify_user_registering(user_id, first_name):
        """Notify user on successful registration"""
        title = "👋 Welcome to Petsona!"
        message = f"Welcome {first_name}! Your account has been successfully created. Start exploring pet services near you!"
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='info',
            link=None,
            related_type='user'
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="Welcome to Petsona - Petsona",
            greeting=f"Welcome {first_name},",
            message=message,
            badge_type='success',
            badge_text='Welcome',
            cta_text="Explore Services",
            cta_link=NotificationManager.get_frontend_url('/services')
        )
        return notif
    
    @staticmethod
    def notify_password_changed(user_id):
        """Notify user when password is changed"""
        title = "🔐 Password Changed"
        message = "Your password has been successfully changed. If this wasn't you, please contact support immediately."
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='password_changed',
            link=None,
            related_type='user'
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="Password Changed - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='info',
            badge_text='Password Changed',
            is_security_alert=True
        )
        return notif
    
    @staticmethod
    def notify_profile_updated(user_id):
        """Notify user when profile is updated"""
        title = "✏️ Profile Updated"
        message = "Your profile has been successfully updated."
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='profile_updated',
            link=None,
            related_type='user'
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="Profile Updated - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='info',
            badge_text='Updated'
        )
        return notif
    
    @staticmethod
    def notify_booking_no_show(user_id, booking_number, merchant_name, related_booking_id=None, from_user_id=None):
        """Notify user when booking is marked as no-show"""
        title = "⚠️ Booking Marked No-Show"
        message = f"Your booking {booking_number} with {merchant_name} has been marked as no-show. Please contact the merchant if this was a mistake."
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='booking_rejected',
            link=None,
            related_id=related_booking_id,
            related_type='booking',
            from_user_id=from_user_id
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="Booking Marked No-Show - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='warning',
            badge_text='No-Show',
            additional_info="Please contact the merchant if this was a mistake or if circumstances prevented you from attending."
        )
        return notif
    
    @staticmethod
    def notify_booking_cancelled_by_customer(user_id, booking_number, customer_name, related_booking_id=None, from_user_id=None):
        """Notify merchant when customer cancels a booking"""
        title = "🚫 Booking Cancelled by Customer"
        message = f"Customer {customer_name} has cancelled booking {booking_number}. Your schedule is now available for this slot."
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='booking_cancelled',
            link=None,
            related_id=related_booking_id,
            related_type='booking',
            from_user_id=from_user_id
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="Booking Cancelled - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='info',
            badge_text='Cancelled'
        )
        return notif
    
    @staticmethod
    def notify_new_message(user_id, sender_name):
        """Notify user when they receive a message"""
        title = "💬 New Message"
        message = f"You have a new message from {sender_name}."
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='new_message',
            link=None,
            related_type='message'
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="New Message from Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='info',
            badge_text='New Message',
            cta_text="View Message",
            cta_link=NotificationManager.get_frontend_url('/messages')
        )
        return notif
    
    # ====== SECURITY & ACCOUNT NOTIFICATIONS ======
    
    @staticmethod
    def notify_account_locked(user_id, failed_attempts=5):
        """Notify user when account is locked due to failed login attempts"""
        title = "🔒 Account Locked"
        message = f"Your account has been locked after {failed_attempts} failed login attempts for security. Please reset your password or contact support to unlock it."
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='account_locked',
            link=None,
            related_type='security'
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="Account Locked - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='danger',
            badge_text='Account Locked',
            cta_text="Reset Password",
            cta_link=NotificationManager.get_frontend_url('/auth/forgot-password'),
            is_security_alert=True
        )
        return notif
    
    @staticmethod
    def notify_2fa_enabled(user_id):
        """Notify user when 2FA is enabled"""
        title = "🛡️ Two-Factor Authentication Enabled"
        message = "Two-factor authentication is now active on your account. You'll need to verify your identity on each login."
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='2fa_enabled',
            link=None,
            related_type='security'
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="2FA Enabled - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='success',
            badge_text='2FA Enabled',
            additional_info="Your account is now more secure with two-factor authentication enabled."
        )
        return notif
    
    @staticmethod
    def notify_2fa_disabled(user_id):
        """Notify user when 2FA is disabled"""
        title = "⚠️ Two-Factor Authentication Disabled"
        message = "Two-factor authentication has been disabled on your account. Your account is now less secure. Consider re-enabling it."
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='2fa_disabled',
            link=None,
            related_type='security'
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="2FA Disabled - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='warning',
            badge_text='2FA Disabled',
            additional_info="We recommend re-enabling two-factor authentication to keep your account secure.",
            is_security_alert=True
        )
        return notif
    
    @staticmethod
    def notify_2fa_reset_suspicious(user_id):
        """Notify user when 2FA is reset due to suspicious activity"""
        title = "🚨 Two-Factor Authentication Reset"
        message = "Your 2FA has been reset due to suspicious activity. Please set up a new authenticator. If this wasn't you, contact support immediately."
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='2fa_reset',
            link=None,
            related_type='security'
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="2FA Reset Due to Suspicious Activity - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='danger',
            badge_text='2FA Reset',
            is_security_alert=True
        )
        return notif
    
    @staticmethod
    def notify_unusual_login_detected(user_id, location_info='', device_info=''):
        """Notify user of unusual login activity"""
        title = "⚠️ Unusual Login Detected"
        message = f"We detected an unusual login to your account."
        if location_info:
            message += f" Location: {location_info}."
        if device_info:
            message += f" Device: {device_info}."
        message += " If this wasn't you, change your password immediately."
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='unusual_login',
            link=None,
            related_type='security'
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="Unusual Login Detected - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='warning',
            badge_text='Unusual Login',
            cta_text="Secure Your Account",
            cta_link=NotificationManager.get_frontend_url('/auth/forgot-password'),
            is_security_alert=True
        )
        return notif
    
    @staticmethod
    def notify_email_changed(user_id, new_email):
        """Notify user when email is changed"""
        title = "✉️ Email Address Changed"
        message = f"Your account email has been changed to {new_email}. If you didn't make this change, verify your account immediately."
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='email_changed',
            link=None,
            related_type='account'
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="Email Address Changed - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='warning',
            badge_text='Email Changed',
            is_security_alert=True
        )
        return notif
    
    @staticmethod
    def notify_role_changed(user_id, new_role):
        """Notify user when their role is changed by admin"""
        title = "👤 Account Role Updated"
        message = f"Your account role has been changed to: {new_role.title()}"
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='role_changed',
            link=None,
            related_type='account'
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="Account Role Updated - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='info',
            badge_text='Role Updated',
            additional_info="If you have any questions about this change, please contact support."
        )
        return notif
    
    # ====== REVIEW NOTIFICATIONS ======
    
    @staticmethod
    def notify_review_received(merchant_user_id, reviewer_name, rating, related_booking_id=None):
        """Notify merchant when they receive a review"""
        title = f"⭐ New {rating}-Star Review"
        message = f"{reviewer_name} left you a review. Check it out to see what they thought of your service!"
        notif = NotificationManager.create_and_emit(
            user_id=merchant_user_id,
            title=title,
            message=message,
            notification_type='review_received',
            link=None,
            related_id=related_booking_id,
            related_type='review'
        )
        NotificationManager.send_notification_email(
            user_id=merchant_user_id,
            subject=f"New {rating}-Star Review - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='success',
            badge_text=f'{rating}-Star Review',
            cta_text="View Review",
            cta_link=NotificationManager.get_frontend_url('/merchant/reviews')
        )
        return notif
    
    @staticmethod
    def notify_review_response_received(user_id, merchant_name, related_booking_id=None):
        """Notify customer when merchant responds to their review"""
        title = f"💬 Response to Your Review"
        message = f"{merchant_name} responded to your review. Check out their reply!"
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='review_responded',
            link=None,
            related_id=related_booking_id,
            related_type='review'
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="Response to Your Review - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='info',
            badge_text='Review Response',
            cta_text="View Response",
            cta_link=NotificationManager.get_frontend_url('/bookings')
        )
        return notif
    
    # ====== MATCHING & RECOMMENDATIONS ======
    
    @staticmethod
    def notify_pet_match_found(user_id, pet_name, compatibility_percentage, match_type='breed'):
        """Notify user when a compatible pet match is found"""
        title = f"💕 New Pet Match Found!"
        message = f"We found a {compatibility_percentage}% compatible {match_type} match for {pet_name}. Check it out!"
        notif = NotificationManager.create_and_emit(
            user_id=user_id,
            title=title,
            message=message,
            notification_type='pet_match_found',
            link=None,
            related_type='match'
        )
        NotificationManager.send_notification_email(
            user_id=user_id,
            subject="New Pet Match Found - Petsona",
            greeting="Hi, {{first_name}} {{last_name}}!",
            message=message,
            badge_type='success',
            badge_text='New Match',
            cta_text="View Match",
            cta_link=NotificationManager.get_frontend_url('/matching')
        )
        return notif
    
    # ====== ADMIN SECURITY ALERTS ======
    
    @staticmethod
    def notify_admin_suspicious_activity(admin_user_id, activity_type, description, affected_users_count=1):
        """Notify admin of suspicious activity that may affect system"""
        title = f"🚨 {activity_type.upper()}: SUSPICIOUS ACTIVITY DETECTED"
        message = f"{description} Affected users: {affected_users_count}. Review audit logs immediately."
        notif = NotificationManager.create_and_emit(
            user_id=admin_user_id,
            title=title,
            message=message,
            notification_type='security_alert',
            link='/admin/audit-logs',
            related_type='security_alert'
        )
        NotificationManager.send_notification_email(
            user_id=admin_user_id,
            subject=f"ALERT: Suspicious Activity Detected - Petsona",
            greeting="Administrator,",
            message=message,
            badge_type='danger',
            badge_text='ALERT',
            cta_text="Review Audit Logs",
            cta_link=NotificationManager.get_frontend_url('/admin/audit-logs'),
            is_security_alert=True
        )
        return notif
    
    @staticmethod
    def notify_admin_security_event(admin_user_id, event_type, user_email, details=''):
        """Notify admin of important security events"""
        title = f"⚠️ SECURITY EVENT: {event_type}"
        message = f"Account: {user_email}. {details} Check audit logs for full details."
        notif = NotificationManager.create_and_emit(
            user_id=admin_user_id,
            title=title,
            message=message,
            notification_type='security_alert',
            link='/admin/audit-logs',
            related_type='security_event'
        )
        NotificationManager.send_notification_email(
            user_id=admin_user_id,
            subject=f"ALERT: Security Event - Petsona",
            greeting="Administrator,",
            message=message,
            badge_type='warning',
            badge_text='ALERT',
            cta_text="Review Audit Logs",
            cta_link=NotificationManager.get_frontend_url('/admin/audit-logs'),
            is_security_alert=True
        )
        return notif
    
    @staticmethod
    def notify_admin_mass_alert(admin_user_ids, alert_title, alert_message, severity='high'):
        """Notify multiple admins of a critical security issue"""
        if not isinstance(admin_user_ids, list):
            admin_user_ids = [admin_user_ids]
        
        notifications = []
        for admin_id in admin_user_ids:
            notif = NotificationManager.create_and_emit(
                user_id=admin_id,
                title=alert_title,
                message=alert_message,
                notification_type='security_alert',
                link='/admin/audit-logs'
            )
            # Send email notification
            badge_type = 'danger' if severity == 'high' else 'warning'
            NotificationManager.send_notification_email(
                user_id=admin_id,
                subject=f"CRITICAL ALERT: {alert_title} - Petsona",
                greeting="Administrator,",
                message=alert_message,
                badge_type=badge_type,
                badge_text='CRITICAL ALERT',
                cta_text="Review Audit Logs",
                cta_link=NotificationManager.get_frontend_url('/admin/audit-logs'),
                is_security_alert=True
            )
            notifications.append(notif)
        
        return notifications

