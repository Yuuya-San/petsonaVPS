"""Message model for user-to-user messaging."""
from datetime import datetime
from app.extensions import db
import pytz
from app.utils.security import encrypt_message, decrypt_message

# Philippine timezone
PH_TZ = pytz.timezone('Asia/Manila')


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    
    # Conversation relationship
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False, index=True)
    conversation = db.relationship('Conversation', back_populates='messages', foreign_keys=[conversation_id])
    
    # Sender and receiver
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])
    
    # Message content (stored encrypted)
    _content = db.Column('content', db.Text, nullable=False)
    
    @property
    def content(self):
        """Get decrypted message content."""
        if not self._content:
            return ''
        return decrypt_message(self._content)
    
    @content.setter
    def content(self, value):
        """Set and encrypt message content."""
        self._content = encrypt_message(value) if value else value
    
    # Status tracking
    is_read = db.Column(db.Boolean, default=False, index=True)
    read_at = db.Column(db.DateTime)
    is_delivered = db.Column(db.Boolean, default=True)
    
    # Soft delete
    is_deleted_by_sender = db.Column(db.Boolean, default=False)
    is_deleted_by_receiver = db.Column(db.Boolean, default=False)
    is_reported = db.Column(db.Boolean, default=False)
    report_reason = db.Column(db.String(255))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def is_visible_to_sender(self):
        """Check if message is visible to sender."""
        return not self.is_deleted_by_sender
    
    @property
    def is_visible_to_receiver(self):
        """Check if message is visible to receiver."""
        return not self.is_deleted_by_receiver
    
    def mark_as_read(self):
        """Mark message as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
            db.session.commit()
    
    def mark_as_delivered(self):
        """Mark message as delivered."""
        if not self.is_delivered:
            self.is_delivered = True
            db.session.commit()
    
    def get_formatted_time(self):
        """Get formatted time in Philippine timezone with mm/dd/yr HH:MM AM/PM."""
        try:
            # Convert UTC to Philippine timezone
            ph_time = self.created_at.replace(tzinfo=pytz.UTC).astimezone(PH_TZ)
            # Format: mm/dd/yr HH:MM AM/PM
            return ph_time.strftime('%m/%d/%y %I:%M %p')
        except:
            # Fallback to original format if pytz fails
            return self.created_at.strftime('%m/%d/%y %I:%M %p')
    
    def get_time_only(self):
        """Get time only in Philippine timezone (HH:MM AM/PM)."""
        try:
            ph_time = self.created_at.replace(tzinfo=pytz.UTC).astimezone(PH_TZ)
            return ph_time.strftime('%I:%M %p')
        except:
            return self.created_at.strftime('%I:%M %p')
    def to_dict(self, current_user_id):
        """Convert message to dictionary for JSON response."""
        sender_photo = None
        if self.sender and self.sender.photo_url:
            from flask import url_for
            sender_photo = url_for('static', filename=self.sender.photo_url, _external=False)
        
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'receiver_id': self.receiver_id,
            'sender_name': self.sender.first_name if self.sender else 'Unknown',
            'sender_photo': sender_photo,
            'content': self.content,
            'is_read': self.is_read,
            'is_delivered': self.is_delivered,
            'is_own_message': self.sender_id == current_user_id,
            'created_at': self.created_at.isoformat(),
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at_formatted': self.get_time_only(),
            'created_at_formatted_full': self.get_formatted_time(),
        }


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    
    # Participants
    user1_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    user2_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    user1 = db.relationship('User', foreign_keys=[user1_id])
    user2 = db.relationship('User', foreign_keys=[user2_id])
    
    # Messages in this conversation
    messages = db.relationship('Message', back_populates='conversation', cascade='all, delete-orphan', foreign_keys='[Message.conversation_id]')
    
    # Conversation status
    last_message_id = db.Column(db.Integer, db.ForeignKey('messages.id'))
    last_message = db.relationship('Message', foreign_keys=[last_message_id])
    
    # Blocking
    blocked_by_user1 = db.Column(db.Boolean, default=False)
    blocked_by_user2 = db.Column(db.Boolean, default=False)
    
    # Archiving
    is_archived_by_user1 = db.Column(db.Boolean, default=False)
    is_archived_by_user2 = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_other_user(self, user_id):
        """Get the other user in the conversation."""
        return self.user2 if self.user1_id == user_id else self.user1
    
    def get_other_user_id(self, user_id):
        """Get the other user ID."""
        return self.user2_id if self.user1_id == user_id else self.user1_id
    
    def is_blocked_for_user(self, user_id):
        """Check if conversation is blocked for this user."""
        if self.user1_id == user_id:
            return self.blocked_by_user2
        return self.blocked_by_user1
    
    def get_unread_count(self, user_id):
        """Get unread message count for user."""
        return Message.query.filter(
            Message.conversation_id == self.id,
            Message.receiver_id == user_id,
            Message.is_read == False,
            Message.is_deleted_by_receiver == False
        ).count()
    
    def get_last_message_preview(self):
        """Get preview of last message."""
        if not self.last_message:
            return "No messages yet"
        
        content = self.last_message.content[:50]
        if len(self.last_message.content) > 50:
            content += "..."
        
        return content
    
    def to_dict(self, current_user_id):
        """Convert conversation to dictionary for JSON response."""
        other_user = self.get_other_user(current_user_id)
        unread_count = self.get_unread_count(current_user_id)
        
        return {
            'id': self.id,
            'other_user_id': other_user.id,
            'other_user_name': f"{other_user.first_name} {other_user.last_name}",
            'other_user_photo': other_user.photo_url,
            'last_message_preview': self.get_last_message_preview(),
            'unread_count': unread_count,
            'last_message_at': self.updated_at.isoformat(),
            'is_blocked': self.is_blocked_for_user(current_user_id),
            'is_archived': (self.is_archived_by_user1 if self.user1_id == current_user_id else self.is_archived_by_user2),
        }
