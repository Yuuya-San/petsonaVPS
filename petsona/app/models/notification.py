"""Notification model for real-time user notifications"""
from datetime import datetime
from app.extensions import db
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)


class Notification(db.Model):
    """
    Notification model for system notifications.
    Uses PH timezone for all timestamps.
    """
    __tablename__ = "notifications"

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # User relationship (recipient)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    user = db.relationship('User', backref=db.backref('notifications', cascade='all, delete-orphan', lazy='dynamic'), foreign_keys=[user_id])
    
    # Sender relationship (from_user_id - optional, nullable for system notifications)
    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    from_user = db.relationship('User', foreign_keys=[from_user_id], backref=db.backref('sent_notifications', lazy='dynamic'))

    # Notification content
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), default='info', index=True)  # info, success, warning, danger, booking, message
    icon = db.Column(db.String(100), default='fas fa-bell')  # FontAwesome icon class
    
    # Related resource
    link = db.Column(db.String(500), nullable=True)  # URL to navigate when clicked
    related_id = db.Column(db.Integer, nullable=True)  # ID of related resource (booking, message, etc.)
    related_type = db.Column(db.String(50), nullable=True)  # Type of related resource (booking, user, merchant, etc.)

    # Status
    is_read = db.Column(db.Boolean, default=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)

    # Timestamps (Philippines timezone)
    created_at = db.Column(db.DateTime, default=get_ph_datetime, index=True)
    updated_at = db.Column(db.DateTime, default=get_ph_datetime, onupdate=get_ph_datetime)
    deleted_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.Index('idx_user_is_read', 'user_id', 'is_read'),
        db.Index('idx_user_created', 'user_id', 'created_at'),
        db.Index('idx_related', 'related_type', 'related_id'),
    )

    def __repr__(self):
        return f'<Notification {self.id} - {self.title} (user={self.user_id})>'

    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = get_ph_datetime()
            db.session.commit()

    def to_dict(self):
        """Convert notification to dictionary for JSON serialization"""
        # Get sender information using from_user_id from users table
        sender_info = None
        
        # First try using the relationship (if joinedload was used)
        if self.from_user:
            sender_info = {
                'id': self.from_user.id,
                'name': f"{self.from_user.first_name} {self.from_user.last_name}".strip(),
                'email': self.from_user.email,
                'photo_url': self.from_user.photo_url
            }
            print(f"[✅ DB] from_user relationship found: {sender_info['name']}, photo_url={sender_info['photo_url']}")
        elif self.from_user_id:
            # Fallback: Query User table directly using from_user_id
            from app.models.user import User
            sender = User.query.filter_by(id=self.from_user_id).first()
            if sender:
                sender_info = {
                    'id': sender.id,
                    'name': f"{sender.first_name} {sender.last_name}".strip(),
                    'email': sender.email,
                    'photo_url': sender.photo_url
                }
                print(f"[✅ DB] from_user_id lookup: {sender_info['name']}, photo_url={sender_info['photo_url']}")
            else:
                print(f"[❌ DB] No user found for from_user_id={self.from_user_id}")
        
        # Format timestamps
        created_time_short = self.created_at.strftime('%I:%M %p') if self.created_at else ''
        created_time_full = self.created_at.strftime('%B %d, %Y at %I:%M %p') if self.created_at else ''
        
        return {
            # Basic info
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'type': self.notification_type,
            'icon': self.icon,
            
            # Display data
            'link': self.link,
            'is_read': self.is_read,
            'time_short': created_time_short,
            'time_full': created_time_full,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            
            # Related resource
            'related_type': self.related_type,
            'related_id': self.related_id,
            
            # Sender information
            'from_user_id': self.from_user_id,
            'from_user': sender_info
        }

    @staticmethod
    def create_notification(user_id, title, message, notification_type='info', icon='fas fa-bell',
                          link=None, related_id=None, related_type=None, from_user_id=None):
        """
        Helper method to create a notification.
        
        Args:
            user_id: User ID to notify (recipient)
            title: Short notification title
            message: Detailed notification message
            notification_type: Type of notification (info, success, warning, danger, booking, message)
            icon: FontAwesome icon class
            link: URL to navigate to when clicked
            related_id: ID of related resource
            related_type: Type of related resource
            from_user_id: User ID of sender/origin (optional, for non-system notifications)
        
        Returns:
            Notification object
        """
        try:
            print(f"\n[DB] Creating notification for user {user_id}: {title}")
            print(f"[DB]   From user: {from_user_id}")
            
            notification = Notification(
                user_id=user_id,
                from_user_id=from_user_id,
                title=title,
                message=message,
                notification_type=notification_type,
                icon=icon,
                link=link,
                related_id=related_id,
                related_type=related_type,
                created_at=get_ph_datetime()
            )
            
            print(f"[DB] Notification object created: {notification}")
            
            db.session.add(notification)
            print(f"[DB] Added to session")
            
            db.session.flush()
            print(f"[DB] Flushed (ID assigned): {notification.id}")
            
            db.session.commit()
            print(f"[DB] ✅ COMMITTED - Notification ID {notification.id} inserted into database")
            
            return notification
        except Exception as e:
            print(f"[DB] ❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            print(f"[DB] Rolled back")
            return None
