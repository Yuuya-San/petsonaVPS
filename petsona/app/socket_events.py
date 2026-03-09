"""Socket.IO event handlers for real-time updates"""
from flask import session, request
from flask_socketio import emit, join_room, leave_room # pyright: ignore[reportMissingModuleSource]
from app.extensions import socketio
from app.models import Species
from flask_login import current_user
import logging
from datetime import datetime
import pytz

# Philippine timezone helper
PH_TZ = pytz.timezone('Asia/Manila')

def get_ph_datetime():
    """Get current datetime in Philippine timezone"""
    return datetime.now(PH_TZ)

logger = logging.getLogger(__name__)

# Store active watchers
active_watchers = {}
# Store active users in conversations
active_users = {}


@socketio.on('connect')
def handle_connect():
    """Handle new Socket.IO connections"""
    sid = request.sid
    if current_user.is_authenticated:
        if current_user.id not in active_users:
            active_users[current_user.id] = []
        active_users[current_user.id].append(sid)
        
        # Join user-specific room for navbar updates
        room = f'user_{current_user.id}'
        from flask_socketio import join_room # pyright: ignore[reportMissingModuleSource]
        join_room(room)
        
        logger.info(f"✅ User {current_user.id} connected: {sid} (joined room: {room})")
    else:
        logger.info(f"✅ Anonymous user connected: {sid}")
    emit('connection_response', {'data': 'Connected to Petsona server'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnections"""
    sid = request.sid
    logger.info(f"❌ Client disconnected: {sid}")
    
    # Clean up any watchers for this client
    if sid in active_watchers:
        del active_watchers[sid]
    
    # Clean up active users and update last_seen
    if current_user.is_authenticated:
        if current_user.id in active_users:
            if sid in active_users[current_user.id]:
                active_users[current_user.id].remove(sid)
        
        # Update last_seen when user disconnects
        current_user.update_last_seen()
        logger.info(f"👤 User {current_user.id} last_seen updated on disconnect")


@socketio.on('watch_species')
def handle_watch_species(data):
    """Register client to watch species vote updates"""
    try:
        species_id = data.get('species_id')
        if not species_id:
            emit('error', {'message': 'Invalid species_id'})
            return
        
        room = f'species_{species_id}'
        join_room(room)
        
        # Store watcher info
        sid = request.sid
        if sid not in active_watchers:
            active_watchers[sid] = []
        active_watchers[sid].append(species_id)
        
        logger.info(f"👁️ Client {sid} watching species {species_id}")
        emit('watch_confirmed', {'species_id': species_id, 'message': f'Now watching species {species_id}'})
        
    except Exception as e:
        logger.error(f"Error watching species: {str(e)}")
        emit('error', {'message': str(e)})


@socketio.on('unwatch_species')
def handle_unwatch_species(data):
    """Unregister client from watching species"""
    try:
        species_id = data.get('species_id')
        if not species_id:
            return
        
        room = f'species_{species_id}'
        leave_room(room)
        
        # Remove from watchers
        sid = request.sid
        if sid in active_watchers and species_id in active_watchers[sid]:
            active_watchers[sid].remove(species_id)
        
        logger.info(f"👁️ Client {sid} stopped watching species {species_id}")
        
    except Exception as e:
        logger.error(f"Error unwatching species: {str(e)}")


# ==================== MESSAGING EVENTS ====================

@socketio.on('join_conversation')
def handle_join_conversation(data):
    """Join a conversation room for real-time messaging."""
    try:
        conversation_id = data.get('conversation_id')
        if not conversation_id or not current_user.is_authenticated:
            emit('error', {'message': 'Invalid request'})
            return
        
        room = f'conversation_{conversation_id}'
        join_room(room)
        
        logger.info(f"👁️ User {current_user.id} joined conversation {conversation_id}")
        emit('user_joined', {
            'user_id': current_user.id,
            'user_name': current_user.first_name,
            'conversation_id': conversation_id
        }, room=room)
        
    except Exception as e:
        logger.error(f"Error joining conversation: {str(e)}")
        emit('error', {'message': str(e)})


@socketio.on('leave_conversation')
def handle_leave_conversation(data):
    """Leave a conversation room."""
    try:
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            return
        
        room = f'conversation_{conversation_id}'
        leave_room(room)
        
        logger.info(f"👁️ User {current_user.id} left conversation {conversation_id}")
        emit('user_left', {
            'user_id': current_user.id,
            'conversation_id': conversation_id
        }, room=room)
        
    except Exception as e:
        logger.error(f"Error leaving conversation: {str(e)}")


@socketio.on('typing')
def handle_typing(data):
    """Broadcast typing indicator."""
    try:
        conversation_id = data.get('conversation_id')
        if not conversation_id or not current_user.is_authenticated:
            return
        
        room = f'conversation_{conversation_id}'
        emit('user_typing', {
            'user_id': current_user.id,
            'user_name': current_user.first_name
        }, room=room, skip_sid=request.sid)
        
    except Exception as e:
        logger.error(f"Error handling typing: {str(e)}")


@socketio.on('stop_typing')
def handle_stop_typing(data):
    """Stop typing indicator."""
    try:
        conversation_id = data.get('conversation_id')
        if not conversation_id or not current_user.is_authenticated:
            return
        
        room = f'conversation_{conversation_id}'
        emit('user_stopped_typing', {
            'user_id': current_user.id
        }, room=room, skip_sid=request.sid)
        
    except Exception as e:
        logger.error(f"Error handling stop typing: {str(e)}")


@socketio.on('user_online')
def handle_user_online(data):
    """Handle user coming online."""
    try:
        conversation_id = data.get('conversation_id')
        other_user_id = data.get('other_user_id')
        
        if not conversation_id or not current_user.is_authenticated:
            return
        
        # Update user's last_seen
        current_user.update_last_seen()
        
        # Add user to active users tracking
        if current_user.id not in active_users:
            active_users[current_user.id] = set()
        active_users[current_user.id].add(request.sid)
        
        # Broadcast to conversation that user is online WITH timestamp
        room = f'conversation_{conversation_id}'
        emit('user_status_changed', {
            'user_id': current_user.id,
            'status': 'online',
            'display_text': 'Active now',
            'is_online': True,
            'timestamp': current_user.last_seen.isoformat() if current_user.last_seen else None
        }, room=room)
        
        logger.info(f"🟢 User {current_user.id} is online in conversation {conversation_id}")
        
    except Exception as e:
        logger.error(f"Error handling user online: {str(e)}")


@socketio.on('user_inactive')
def handle_user_inactive(data):
    """Handle user becoming inactive."""
    try:
        conversation_id = data.get('conversation_id')
        
        if not conversation_id or not current_user.is_authenticated:
            return
        
        # Update user's last_seen
        current_user.update_last_seen()
        
        # Format the offline status
        status_info = current_user.get_online_status(is_online=False)
        
        # Broadcast to conversation that user is offline (to ALL users including sender)
        room = f'conversation_{conversation_id}'
        emit('user_status_changed', {
            'user_id': current_user.id,
            'status': 'offline',
            'display_text': status_info['display_text'],
            'is_online': False,
            'timestamp': status_info['timestamp']
        }, room=room)
        
        logger.info(f"🔴 User {current_user.id} is inactive in conversation {conversation_id}")
        
    except Exception as e:
        logger.error(f"Error handling user inactive: {str(e)}")


@socketio.on('get_user_status')
def handle_get_user_status(data):
    """Get current user's online status."""
    try:
        from app.models import User
        
        other_user_id = data.get('user_id')
        
        if not other_user_id:
            emit('error', {'message': 'Invalid user_id'})
            return
        
        other_user = User.query.get(other_user_id)
        if not other_user:
            emit('error', {'message': 'User not found'})
            return
        
        # Check if user is currently connected (has active socket connections)
        is_connected = other_user_id in active_users and len(active_users[other_user_id]) > 0
        
        # Strict check: User is ONLY "online" if has active connection
        is_online = is_connected
        
        # Log detailed info
        if other_user.last_seen:
            now_ph = get_ph_datetime()
            last_seen_ph = other_user.last_seen.replace(tzinfo=pytz.UTC).astimezone(PH_TZ)
            time_since_last_seen_minutes = (now_ph - last_seen_ph).total_seconds() / 60
            logger.info(f"👤 User {other_user_id}: last_seen={time_since_last_seen_minutes:.1f}m ago, is_connected={is_connected}, is_online={is_online}")
        
        # Get status info
        status_info = other_user.get_online_status(is_online=is_online)
        
        emit('user_status', {
            'user_id': other_user_id,
            **status_info
        })
        
        logger.info(f"📤 Status for user {other_user_id}: is_online={is_online}")
        
    except Exception as e:
        logger.error(f"Error getting user status: {str(e)}")
        emit('error', {'message': str(e)})


def broadcast_species_vote_update(species_id, new_vote_count):
    """Broadcast vote count update to all clients watching this species"""
    try:
        room = f'species_{species_id}'
        logger.info(f"📡 Broadcasting vote update for species {species_id}: {new_vote_count} votes")
        socketio.emit(
            'vote_update',
            {
                'species_id': species_id,
                'vote_count': new_vote_count,
                'timestamp': get_ph_datetime().isoformat()
            },
            room=room
        )
    except Exception as e:
        logger.error(f"Error broadcasting vote update: {str(e)}")


def broadcast_breed_vote_update(breed_id, total_votes, voted, user_id):
    """Broadcast breed vote update to all connected clients"""
    try:
        logger.info(f"📡 Broadcasting breed vote update for breed {breed_id}: {total_votes} votes")
        socketio.emit(
            'breed_vote_update',
            {
                'breed_id': breed_id,
                'total_votes': total_votes,
                'voted': voted,
                'user_id': user_id,
                'timestamp': get_ph_datetime().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Error broadcasting breed vote update: {str(e)}")


def broadcast_new_message(conversation_id, message_data):
    """Broadcast new message to conversation room."""
    try:
        room = f'conversation_{conversation_id}'
        logger.info(f"📡 Broadcasting new message in conversation {conversation_id}")
        socketio.emit('new_message', message_data, room=room)
    except Exception as e:
        logger.error(f"Error broadcasting new message: {str(e)}")


def notify_message_read(conversation_id, message_id, read_at):
    """Notify users that a message has been read."""
    try:
        room = f'conversation_{conversation_id}'
        logger.info(f"📡 Broadcasting message read notification for message {message_id}")
        socketio.emit('message_read', {
            'message_id': message_id,
            'read_at': read_at
        }, room=room)
    except Exception as e:
        logger.error(f"Error notifying message read: {str(e)}")


def notify_unread_message_count(recipient_id, unread_count):
    """Notify a specific user about their unread message count."""
    try:
        logger.info(f"📡 Notifying user {recipient_id} of {unread_count} unread messages")
        socketio.emit('unread_count_update', {
            'unread_count': unread_count,
            'timestamp': get_ph_datetime().isoformat()
        }, room=f'user_{recipient_id}')
    except Exception as e:
        logger.error(f"Error notifying unread count: {str(e)}")


def broadcast_message_to_navbar(recipient_id, conversation_id, sender_id, sender_name, sender_avatar, message_preview):
    """Broadcast new message to recipient's navbar for live update."""
    try:
        logger.info(f"📡 Broadcasting message navbar update for user {recipient_id}")
        socketio.emit('navbar_message_update', {
            'conversation_id': conversation_id,
            'sender_id': sender_id,
            'sender_name': sender_name,
            'sender_avatar': sender_avatar,
            'message_preview': message_preview,
            'timestamp': get_ph_datetime().isoformat()
        }, room=f'user_{recipient_id}')
    except Exception as e:
        logger.error(f"Error broadcasting navbar message update: {str(e)}")


# ==================== NOTIFICATION EVENTS ====================

@socketio.on('get_notifications')
def handle_get_notifications():
    """Get all notifications (read and unread) for current user"""
    try:
        if not current_user.is_authenticated:
            logger.warning('get_notifications: User not authenticated')
            emit('error', {'message': 'User not authenticated'})
            return
        
        logger.info(f"📡 Fetching notifications for user {current_user.id}")
        from app.models import Notification
        from sqlalchemy.orm import joinedload
        
        # Get last 20 notifications with eager loading of from_user relationship
        notifications = Notification.query.options(
            joinedload(Notification.from_user)
        ).filter(
            Notification.user_id == current_user.id,
            Notification.deleted_at.is_(None)
        ).order_by(Notification.created_at.desc()).limit(20).all()
        
        logger.info(f"✓ Found {len(notifications)} notifications for user {current_user.id}")
        
        # Build notification list with logging
        notif_list = []
        for notif in notifications:
            notif_dict = notif.to_dict()
            notif_list.append(notif_dict)
            # Log sender info
            if notif_dict.get('from_user'):
                sender = notif_dict['from_user']
                logger.info(f"  📧 Notif {notif.id}: from {sender.get('name')} (photo_url={sender.get('photo_url')})")
        
        # Count total unread
        unread_count = Notification.query.filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
            Notification.deleted_at.is_(None)
        ).count()
        
        emit('notifications_list', {
            'notifications': notif_list,
            'unread_count': unread_count,
            'timestamp': get_ph_datetime().isoformat()
        })
        
        logger.info(f"📡 Sent {len(notif_list)} notifications to user {current_user.id}")
        
    except Exception as e:
        logger.error(f"Error fetching notifications: {str(e)}")
        emit('error', {'message': str(e)})


@socketio.on('mark_notification_read')
def handle_mark_notification_read(data):
    """Mark a notification as read"""
    try:
        if not current_user.is_authenticated:
            emit('error', {'message': 'User not authenticated'})
            return
        
        from app.models import Notification
        
        notification_id = data.get('notification_id')
        if not notification_id:
            emit('error', {'message': 'Invalid notification_id'})
            return
        
        notification = Notification.query.filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        ).first()
        
        if notification:
            notification.mark_as_read()
            
            # Get updated unread count
            unread_count = Notification.query.filter(
                Notification.user_id == current_user.id,
                Notification.is_read == False,
                Notification.deleted_at.is_(None)
            ).count()
            
            # Emit update to user
            emit('notification_marked_read', {
                'notification_id': notification_id,
                'unread_count': unread_count,
                'timestamp': get_ph_datetime().isoformat()
            }, room=f'user_{current_user.id}')
            
            logger.info(f"✅ Notification {notification_id} marked as read for user {current_user.id}")
        else:
            emit('error', {'message': 'Notification not found'})
            
    except Exception as e:
        logger.error(f"Error marking notification as read: {str(e)}")
        emit('error', {'message': str(e)})


@socketio.on('get_unread_count')
def handle_get_unread_count():
    """Get count of unread notifications"""
    try:
        if not current_user.is_authenticated:
            logger.warning('get_unread_count: User not authenticated')
            emit('error', {'message': 'User not authenticated'})
            return
        
        logger.info(f"📡 Fetching unread count for user {current_user.id}")
        from app.models import Notification
        
        unread_count = Notification.query.filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
            Notification.deleted_at.is_(None)
        ).count()
        
        logger.info(f"✓ User {current_user.id} has {unread_count} unread notifications")
        
        emit('unread_count', {
            'count': unread_count,
            'timestamp': get_ph_datetime().isoformat()
        })
        
        logger.info(f"📡 Unread notification count for user {current_user.id}: {unread_count}")
        
    except Exception as e:
        logger.error(f"Error fetching unread count: {str(e)}")
        emit('error', {'message': str(e)})


@socketio.on('mark_all_notifications_read')
def handle_mark_all_notifications_read():
    """Mark all notifications as read"""
    try:
        if not current_user.is_authenticated:
            emit('error', {'message': 'User not authenticated'})
            return
        
        from app.models import Notification
        
        # Update all unread notifications
        notifications = Notification.query.filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
            Notification.deleted_at.is_(None)
        ).all()
        
        for notification in notifications:
            notification.mark_as_read()
        
        emit('all_notifications_marked_read', {
            'count': len(notifications),
            'timestamp': get_ph_datetime().isoformat()
        }, room=f'user_{current_user.id}')
        
        logger.info(f"✅ All {len(notifications)} notifications marked as read for user {current_user.id}")
        
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {str(e)}")
        emit('error', {'message': str(e)})



@socketio.on('get_notification_detail')
def handle_get_notification_detail(data):
    """Get full details of a specific notification"""
    try:
        if not current_user.is_authenticated:
            emit('error', {'message': 'User not authenticated'})
            return
        
        from app.models import Notification
        
        notification_id = data.get('notification_id')
        if not notification_id:
            emit('error', {'message': 'Invalid notification_id'})
            return
        
        from sqlalchemy.orm import joinedload
        notification = Notification.query.options(
            joinedload(Notification.from_user)
        ).filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        ).first()
        
        if notification:
            notif_dict = notification.to_dict()
            # Log sender info
            if notif_dict.get('from_user'):
                sender = notif_dict['from_user']
                logger.info(f"📧 MODAL Notif {notification_id}: from {sender.get('name')} (photo_url={sender.get('photo_url')})")
            
            logger.info(f"📋 Sent full notification detail for notification {notification_id} to user {current_user.id}")
            emit('notification_detail', {
                'notification': notif_dict,
                'timestamp': get_ph_datetime().isoformat()
            })
        else:
            emit('error', {'message': 'Notification not found'})
            
    except Exception as e:
        logger.error(f"Error fetching notification detail: {str(e)}")
        emit('error', {'message': str(e)})


def notify_user(user_id, title, message, notification_type='info', link=None, icon=None):
    """
    Emit notification to a specific user via SocketIO.
    Used by NotificationManager.create_and_emit() for real-time delivery.
    """
    try:
        room = f'user_{user_id}'
        logger.info(f"📡 Emitting notification to user {user_id} in room {room}")
        socketio.emit('new_notification_received', {
            'title': title,
            'message': message,
            'type': notification_type,
            'icon': icon or 'fas fa-bell',
            'link': link,
            'timestamp': get_ph_datetime().isoformat()
        }, room=room)
    except Exception as e:
        logger.error(f"Error notifying user {user_id}: {str(e)}")


