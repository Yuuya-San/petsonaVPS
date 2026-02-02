"""Socket.IO event handlers for real-time updates"""
from flask import session, request
from flask_socketio import emit, join_room, leave_room
from app.extensions import socketio
from app.models import Species
from flask_login import current_user
import logging

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
        logger.info(f"✅ User {current_user.id} connected: {sid}")
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
    
    # Clean up active users
    if current_user.is_authenticated and current_user.id in active_users:
        if sid in active_users[current_user.id]:
            active_users[current_user.id].remove(sid)


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


def broadcast_vote_update(species_id, new_vote_count):
    """Broadcast vote count update to all clients watching this species"""
    try:
        room = f'species_{species_id}'
        logger.info(f"📡 Broadcasting vote update for species {species_id}: {new_vote_count} votes")
        socketio.emit(
            'vote_update',
            {
                'species_id': species_id,
                'vote_count': new_vote_count,
                'timestamp': __import__('datetime').datetime.utcnow().isoformat()
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
                'timestamp': __import__('datetime').datetime.utcnow().isoformat()
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

