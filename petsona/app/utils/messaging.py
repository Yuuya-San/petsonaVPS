"""Messaging utilities and helper functions."""
from app.models.message import Message, Conversation
from app.models.user import User
from app.extensions import db
from flask import current_app
from datetime import datetime, timedelta


def get_or_create_conversation(user1_id, user2_id):
    """
    Get or create a conversation between two users.
    Ensures consistent ordering (smaller ID first).
    """
    # Ensure consistent ordering
    if user1_id > user2_id:
        user1_id, user2_id = user2_id, user1_id
    
    conversation = Conversation.query.filter(
        Conversation.user1_id == user1_id,
        Conversation.user2_id == user2_id
    ).first()
    
    if not conversation:
        conversation = Conversation(
            user1_id=user1_id,
            user2_id=user2_id
        )
        db.session.add(conversation)
        db.session.commit()
    
    return conversation


def create_message(conversation_id, sender_id, receiver_id, content):
    """Create a new message."""
    try:
        message = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
            is_read=False,
            is_delivered=True
        )
        
        db.session.add(message)
        
        # Update conversation's last_message_id
        conversation = Conversation.query.get(conversation_id)
        if conversation:
            conversation.last_message_id = message.id
            conversation.updated_at = datetime.utcnow()
        
        db.session.commit()
        return message
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating message: {str(e)}")
        return None


def get_user_inbox(user_id, page=1, per_page=20, include_archived=False):
    """
    Get user's inbox with conversations.
    Returns paginated conversations with unread counts.
    """
    query = Conversation.query.filter(
        db.or_(
            Conversation.user1_id == user_id,
            Conversation.user2_id == user_id
        )
    )
    
    # Filter archived if needed
    if not include_archived:
        query = query.filter(
            db.or_(
                db.and_(
                    Conversation.user1_id == user_id,
                    Conversation.is_archived_by_user1 == False
                ),
                db.and_(
                    Conversation.user2_id == user_id,
                    Conversation.is_archived_by_user2 == False
                )
            )
        )
    
    # Order by most recent message
    query = query.order_by(Conversation.updated_at.desc())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return pagination


def get_conversation_messages(conversation_id, user_id, page=1, per_page=50):
    """
    Get paginated messages for a conversation.
    Respects soft deletes (messages deleted by each user).
    """
    query = Message.query.filter(
        Message.conversation_id == conversation_id
    )
    
    # Filter based on user's perspective
    # Show messages not deleted by this user
    query = query.filter(
        db.or_(
            db.and_(Message.sender_id == user_id, Message.is_deleted_by_sender == False),
            db.and_(Message.receiver_id == user_id, Message.is_deleted_by_receiver == False)
        )
    )
    
    # Order by timestamp
    query = query.order_by(Message.created_at.asc())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return pagination


def mark_conversation_messages_as_read(conversation_id, user_id):
    """Mark all unread messages from a conversation as read for a user."""
    try:
        messages = Message.query.filter(
            Message.conversation_id == conversation_id,
            Message.receiver_id == user_id,
            Message.is_read == False
        ).all()
        
        for message in messages:
            message.is_read = True
            message.read_at = datetime.utcnow()
        
        db.session.commit()
        return len(messages)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking messages as read: {str(e)}")
        return 0


def block_user(blocker_id, blocked_id, conversation_id):
    """Block a user from a conversation."""
    try:
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return False
        
        if conversation.user1_id == blocker_id:
            conversation.blocked_by_user1 = True
        elif conversation.user2_id == blocker_id:
            conversation.blocked_by_user2 = True
        else:
            return False
        
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error blocking user: {str(e)}")
        return False


def unblock_user(unlocker_id, conversation_id):
    """Unblock a user in a conversation."""
    try:
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return False
        
        if conversation.user1_id == unlocker_id:
            conversation.blocked_by_user1 = False
        elif conversation.user2_id == unlocker_id:
            conversation.blocked_by_user2 = False
        else:
            return False
        
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error unblocking user: {str(e)}")
        return False


def archive_conversation(user_id, conversation_id):
    """Archive a conversation for a user."""
    try:
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return False
        
        if conversation.user1_id == user_id:
            conversation.is_archived_by_user1 = True
        elif conversation.user2_id == user_id:
            conversation.is_archived_by_user2 = True
        else:
            return False
        
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error archiving conversation: {str(e)}")
        return False


def unarchive_conversation(user_id, conversation_id):
    """Unarchive a conversation for a user."""
    try:
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return False
        
        if conversation.user1_id == user_id:
            conversation.is_archived_by_user1 = False
        elif conversation.user2_id == user_id:
            conversation.is_archived_by_user2 = False
        else:
            return False
        
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error unarchiving conversation: {str(e)}")
        return False


def delete_message_for_user(message_id, user_id):
    """Soft delete a message for a specific user."""
    try:
        message = Message.query.get(message_id)
        if not message:
            return False
        
        if message.sender_id == user_id:
            message.is_deleted_by_sender = True
        elif message.receiver_id == user_id:
            message.is_deleted_by_receiver = True
        else:
            return False
        
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting message: {str(e)}")
        return False


def report_message(message_id, reporter_id, reason, details):
    """Report a message for violating community guidelines."""
    try:
        message = Message.query.get(message_id)
        if not message:
            return False
        
        # Prevent self-reporting
        if message.sender_id == reporter_id:
            return False
        
        message.is_reported = True
        message.report_reason = f"{reason}: {details}" if details else reason
        
        db.session.commit()
        
        # Log for admin review
        current_app.logger.warning(
            f"Message reported - Message ID: {message_id}, Reporter: {reporter_id}, "
            f"Reason: {message.report_reason}"
        )
        
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error reporting message: {str(e)}")
        return False


def get_unread_count(user_id):
    """Get total unread message count for user."""
    return Message.query.filter(
        Message.receiver_id == user_id,
        Message.is_read == False,
        Message.is_deleted_by_receiver == False
    ).count()


def format_time_ago(dt):
    """Format datetime as 'X time ago'."""
    if not dt:
        return "Unknown"
    
    now = datetime.utcnow()
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes}m ago" if minutes > 1 else "1m ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours}h ago" if hours > 1 else "1h ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days}d ago" if days > 1 else "1d ago"
    else:
        return dt.strftime('%b %d')


def is_user_blocked(user_id, other_user_id, conversation_id):
    """Check if user is blocked by the other user."""
    conversation = Conversation.query.get(conversation_id)
    if not conversation:
        return False
    
    # Check if current user is blocked from receiving messages
    return conversation.is_blocked_for_user(user_id)
