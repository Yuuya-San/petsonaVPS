"""Socket.IO event handlers for real-time updates"""
from flask import session, request
from flask_socketio import emit, join_room, leave_room
from app.extensions import socketio
from app.models import Species
import logging

logger = logging.getLogger(__name__)

# Store active watchers
active_watchers = {}


@socketio.on('connect')
def handle_connect():
    """Handle new Socket.IO connections"""
    sid = request.sid
    logger.info(f"✅ Client connected: {sid}")
    emit('connection_response', {'data': 'Connected to vote update server'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnections"""
    sid = request.sid
    logger.info(f"❌ Client disconnected: {sid}")
    
    # Clean up any watchers for this client
    if sid in active_watchers:
        del active_watchers[sid]


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
