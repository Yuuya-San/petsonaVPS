"""
Redis-based Session and Message Queue Manager for Production Deployments
Enables distributed Socket.IO across multiple server instances
"""

import os
import logging
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)

try:
    import redis # pyright: ignore[reportMissingImports]
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


class RedisManager:
    """
    Manages Redis connections for distributed socket sessions and message queuing
    Provides fallback to in-memory storage if Redis is unavailable
    """
    
    def __init__(self, url: Optional[str] = None, use_redis: bool = True):
        """
        Initialize Redis manager
        
        Args:
            url: Redis connection URL (default: from environment or localhost)
            use_redis: Whether to use Redis (fallback to in-memory if unavailable)
        """
        self.use_redis = use_redis and REDIS_AVAILABLE
        self.client = None
        self.in_memory_store = {}  # Fallback storage
        
        if self.use_redis:
            try:
                redis_url = url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
                self.client = redis.from_url(redis_url)
                
                # Test connection
                self.client.ping()
                logger.info(f"✅ Connected to Redis: {redis_url}")
            except Exception as e:
                logger.warning(f"❌ Redis connection failed: {e}. Using in-memory storage.")
                self.use_redis = False
        else:
            logger.info("ℹ️  Using in-memory storage for sessions")
    
    def set_session(self, session_id: str, data: Dict[str, Any], ttl: int = 3600):
        """
        Store session data with optional TTL
        
        Args:
            session_id: Unique session identifier
            data: Session data dictionary
            ttl: Time-to-live in seconds (default: 1 hour)
        """
        try:
            if self.use_redis and self.client:
                self.client.setex(
                    f"session:{session_id}",
                    ttl,
                    json.dumps(data)
                )
            else:
                self.in_memory_store[session_id] = {
                    'data': data,
                    'ttl': ttl
                }
        except Exception as e:
            logger.error(f"Error storing session: {e}")
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """
        Retrieve session data
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Session data dictionary or None if not found
        """
        try:
            if self.use_redis and self.client:
                data = self.client.get(f"session:{session_id}")
                if data:
                    return json.loads(data)
            else:
                if session_id in self.in_memory_store:
                    return self.in_memory_store[session_id]['data']
        except Exception as e:
            logger.error(f"Error retrieving session: {e}")
        
        return None
    
    def delete_session(self, session_id: str):
        """Delete session data"""
        try:
            if self.use_redis and self.client:
                self.client.delete(f"session:{session_id}")
            else:
                self.in_memory_store.pop(session_id, None)
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
    
    def queue_message(self, queue_name: str, message: Dict[str, Any]):
        """
        Queue a message for processing (used for distributed message handling)
        
        Args:
            queue_name: Name of the queue
            message: Message data
        """
        try:
            if self.use_redis and self.client:
                self.client.rpush(
                    f"queue:{queue_name}",
                    json.dumps(message)
                )
            else:
                if queue_name not in self.in_memory_store:
                    self.in_memory_store[queue_name] = []
                self.in_memory_store[queue_name].append(message)
        except Exception as e:
            logger.error(f"Error queuing message: {e}")
    
    def dequeue_message(self, queue_name: str) -> Optional[Dict]:
        """
        Dequeue and process a message
        
        Args:
            queue_name: Name of the queue
            
        Returns:
            Message data or None if queue empty
        """
        try:
            if self.use_redis and self.client:
                data = self.client.lpop(f"queue:{queue_name}")
                if data:
                    return json.loads(data)
            else:
                if queue_name in self.in_memory_store and self.in_memory_store[queue_name]:
                    return self.in_memory_store[queue_name].pop(0)
        except Exception as e:
            logger.error(f"Error dequeuing message: {e}")
        
        return None
    
    def publish(self, channel: str, message: Dict[str, Any]):
        """
        Publish message to Redis pub/sub channel
        
        Args:
            channel: Channel name
            message: Message data
        """
        try:
            if self.use_redis and self.client:
                self.client.publish(channel, json.dumps(message))
                logger.debug(f"Published to {channel}")
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Redis connection statistics"""
        if self.use_redis and self.client:
            try:
                info = self.client.info()
                return {
                    'status': 'connected',
                    'used_memory_mb': info['used_memory'] / (1024 * 1024),
                    'connected_clients': info['connected_clients'],
                    'total_connections': info.get('total_connections_received', 'N/A')
                }
            except Exception as e:
                return {'status': 'error', 'message': str(e)}
        else:
            return {
                'status': 'in-memory',
                'stored_items': len(self.in_memory_store),
                'note': 'Not using Redis - data not shared across instances'
            }


class SocketIOMessageQueue:
    """
    Message queue for Socket.IO broadcasts in distributed environments
    Allows coordinating broadcasts across multiple server instances
    """
    
    def __init__(self, redis_manager: RedisManager):
        self.redis = redis_manager
        self.queue_name = 'socketio:broadcasts'
    
    def enqueue_broadcast(self, room: str, event: str, data: Dict[str, Any]):
        """
        Queue a broadcast message for all server instances
        
        Args:
            room: Socket.IO room name
            event: Event name
            data: Event data
        """
        message = {
            'room': room,
            'event': event,
            'data': data,
            'timestamp': str(datetime.now())
        }
        self.redis.queue_message(self.queue_name, message)
        logger.debug(f"Queued broadcast to {room}: {event}")
    
    def process_broadcasts(self, socketio_instance):
        """
        Process queued broadcasts (should be called periodically in background task)
        
        Args:
            socketio_instance: The Flask-SocketIO instance
        """
        message = self.redis.dequeue_message(self.queue_name)
        while message:
            try:
                socketio_instance.emit(
                    message['event'],
                    message['data'],
                    room=message['room']
                )
                logger.debug(f"Processed broadcast to {message['room']}")
            except Exception as e:
                logger.error(f"Error processing broadcast: {e}")
            
            message = self.redis.dequeue_message(self.queue_name)


# ==================== INITIALIZATION ====================

def init_redis_for_socketio(app, socketio, async_mode='threading'):
    """
    Initialize Redis for Flask-SocketIO in distributed deployments
    
    Args:
        app: Flask application instance
        socketio: Flask-SocketIO instance
        async_mode: Async mode to use ('threading' or 'gevent')
    """
    use_redis = app.config.get('SOCKETIO_USE_REDIS', True)
    redis_url = app.config.get('SOCKETIO_REDIS_URL', None)
    
    if not use_redis:
        logger.info("Redis support disabled for Socket.IO")
        socketio.init_app(app, async_mode='gevent')
        return None
    
    try:
        # Create Redis manager
        redis_manager = RedisManager(redis_url, use_redis=use_redis)
        
        # Configure Socket.IO to use Redis message queue (if available)
        if redis_manager.use_redis:
            try:
                socketio.init_app(
                    app,
                    async_mode='gevent',
                    message_queue=redis_url or 'redis://localhost:6379/1'
                )
                logger.info("✅ Socket.IO configured with Redis message queue")
            except Exception as e:
                logger.warning(f"Could not configure Socket.IO Redis queue: {e}")
                socketio.init_app(app, async_mode=async_mode)
        else:
            socketio.init_app(app, async_mode=async_mode)
        
        return redis_manager
    
    except Exception as e:
        logger.error(f"Error initializing Redis: {e}")
        socketio.init_app(app, async_mode=async_mode)
        return None


# Export instances
from datetime import datetime
