"""
Socket.IO Utilities - Rate limiting, connection pooling, and event optimization
Production-ready utilities to prevent unnecessary requests and optimize performance
"""

import time
from functools import wraps
from typing import Dict, Set, Callable, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# ==================== SOCKET EVENT RATE LIMITER ====================
class SocketEventRateLimiter:
    """
    Rate limiter for socket events to prevent abuse and unnecessary requests
    Uses token bucket algorithm with per-client rate limiting
    """
    
    def __init__(self, max_events_per_second: float = 10.0, 
                 bucket_capacity: int = 50):
        """
        Initialize rate limiter
        
        Args:
            max_events_per_second: Tokens added per second
            bucket_capacity: Maximum tokens in bucket
        """
        self.max_events_per_second = max_events_per_second
        self.bucket_capacity = bucket_capacity
        self.buckets: Dict[str, Dict] = {}  # client_id -> {tokens, last_update}
        
    def _get_bucket(self, client_id: str) -> Dict:
        """Get or create rate limit bucket for client"""
        if client_id not in self.buckets:
            self.buckets[client_id] = {
                'tokens': self.bucket_capacity,
                'last_update': time.time(),
                'rejected_count': 0
            }
        return self.buckets[client_id]
    
    def is_allowed(self, client_id: str) -> bool:
        """
        Check if event from client is allowed
        Returns True if within rate limit, False otherwise
        """
        bucket = self._get_bucket(client_id)
        now = time.time()
        
        # Add tokens based on elapsed time
        time_passed = now - bucket['last_update']
        bucket['tokens'] = min(
            self.bucket_capacity,
            bucket['tokens'] + time_passed * self.max_events_per_second
        )
        bucket['last_update'] = now
        
        # Check if we have tokens
        if bucket['tokens'] >= 1:
            bucket['tokens'] -= 1
            return True
        
        bucket['rejected_count'] += 1
        if bucket['rejected_count'] % 10 == 0:  # Log every 10th rejection
            logger.warning(f"Rate limit exceeded for client {client_id}")
        
        return False
    
    def cleanup_inactive(self, max_age_seconds: int = 3600):
        """Remove rate limit buckets for inactive clients"""
        now = time.time()
        inactive_clients = [
            client_id for client_id, bucket in self.buckets.items()
            if now - bucket['last_update'] > max_age_seconds
        ]
        for client_id in inactive_clients:
            del self.buckets[client_id]
        
        if inactive_clients:
            logger.info(f"Cleaned up {len(inactive_clients)} inactive client buckets")


# ==================== CONNECTION POOL MANAGER ====================
class SocketConnectionPool:
    """
    Manages socket connections to prevent memory leaks and optimize resources
    Tracks active connections and provides cleanup utilities
    """
    
    def __init__(self):
        self.connections: Dict[str, Dict] = {}  # sid -> {user_id, rooms, connected_at}
        
    def add_connection(self, sid: str, user_id: Optional[int] = None, 
                       metadata: Optional[Dict] = None):
        """Register a new socket connection"""
        self.connections[sid] = {
            'user_id': user_id,
            'rooms': set(),
            'connected_at': datetime.now(),
            'last_activity': datetime.now(),
            'metadata': metadata or {}
        }
        logger.debug(f"Connection added: {sid} (user: {user_id})")
    
    def remove_connection(self, sid: str):
        """Unregister a socket connection"""
        if sid in self.connections:
            duration = datetime.now() - self.connections[sid]['connected_at']
            user_id = self.connections[sid]['user_id']
            del self.connections[sid]
            logger.debug(f"Connection removed: {sid} (user: {user_id}, duration: {duration.total_seconds():.1f}s)")
    
    def add_room(self, sid: str, room: str):
        """Add socket to room"""
        if sid in self.connections:
            self.connections[sid]['rooms'].add(room)
    
    def remove_room(self, sid: str, room: str):
        """Remove socket from room"""
        if sid in self.connections:
            self.connections[sid]['rooms'].discard(room)
    
    def update_activity(self, sid: str):
        """Update last activity timestamp"""
        if sid in self.connections:
            self.connections[sid]['last_activity'] = datetime.now()
    
    def get_connections_by_user(self, user_id: int) -> Set[str]:
        """Get all connection SIDs for a user"""
        return {
            sid for sid, conn in self.connections.items()
            if conn['user_id'] == user_id
        }
    
    def get_idle_connections(self, idle_seconds: int = 300) -> Set[str]:
        """Get connections idle for longer than specified seconds"""
        now = datetime.now()
        return {
            sid for sid, conn in self.connections.items()
            if (now - conn['last_activity']).total_seconds() > idle_seconds
        }
    
    def get_stats(self) -> Dict:
        """Get connection pool statistics"""
        now = datetime.now()
        connections_by_user = {}
        
        for sid, conn in self.connections.items():
            user_id = conn['user_id']
            if user_id not in connections_by_user:
                connections_by_user[user_id] = 0
            connections_by_user[user_id] += 1
        
        return {
            'total_connections': len(self.connections),
            'total_users': len(connections_by_user),
            'avg_connections_per_user': (
                sum(connections_by_user.values()) / len(connections_by_user)
                if connections_by_user else 0
            ),
            'connections_by_user': connections_by_user
        }


# ==================== EVENT DEDUPLICATION ====================
class EventDeduplicator:
    """
    Prevents duplicate events from being processed
    Useful for preventing unnecessary database queries
    """
    
    def __init__(self, ttl_seconds: int = 60):
        self.events: Dict[str, float] = {}  # event_hash -> timestamp
        self.ttl = ttl_seconds
    
    def is_duplicate(self, event_key: str) -> bool:
        """
        Check if event is a duplicate
        Returns True if duplicate, False if new event
        """
        now = time.time()
        
        # Clean old entries
        expired = [k for k, t in self.events.items() if now - t > self.ttl]
        for k in expired:
            del self.events[k]
        
        if event_key in self.events:
            return True
        
        self.events[event_key] = now
        return False


# ==================== SOCKET EVENT RATE LIMIT DECORATOR ====================
def socket_rate_limit(limiter: SocketEventRateLimiter, 
                      rate_events_per_second: float = 10.0):
    """
    Decorator for socket event handlers to apply rate limiting
    
    Usage:
        @socketio.on('some_event')
        @socket_rate_limit(limiter, rate_events_per_second=5)
        def handle_some_event(data):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request
            
            # Get client ID (socket session ID)
            client_id = request.sid
            
            # Check rate limit
            if not limiter.is_allowed(client_id):
                logger.warning(f"Rate limit exceeded for {func.__name__} from client {client_id}")
                return {'error': 'Too many requests'}
            
            # Call original handler
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


# ==================== BATCH EVENT PROCESSOR ====================
class BatchEventProcessor:
    """
    Batches events to reduce database queries and network overhead
    Useful for high-frequency events like typing indicators
    """
    
    def __init__(self, batch_size: int = 10, flush_interval_ms: int = 100):
        self.batch_size = batch_size
        self.flush_interval = flush_interval_ms / 1000.0
        self.batch: Dict[str, list] = {}
        self.last_flush: Dict[str, float] = {}
    
    def add_event(self, event_type: str, data: Dict) -> Optional[list]:
        """
        Add event to batch, returns batch if ready to flush
        """
        if event_type not in self.batch:
            self.batch[event_type] = []
            self.last_flush[event_type] = time.time()
        
        self.batch[event_type].append(data)
        now = time.time()
        
        # Check if batch should be flushed
        should_flush = (
            len(self.batch[event_type]) >= self.batch_size or
            (now - self.last_flush[event_type]) >= self.flush_interval
        )
        
        if should_flush:
            batch_data = self.batch[event_type].copy()
            self.batch[event_type] = []
            self.last_flush[event_type] = now
            return batch_data
        
        return None


# ==================== GLOBAL INSTANCES ====================
# Initialize global rate limiter (10 events per second per client, max 50 in burst)
socket_rate_limiter = SocketEventRateLimiter(
    max_events_per_second=10.0,
    bucket_capacity=50
)

# Initialize connection pool
socket_connection_pool = SocketConnectionPool()

# Initialize event deduplicator
event_deduplicator = EventDeduplicator(ttl_seconds=60)

# Initialize batch processor
batch_event_processor = BatchEventProcessor(batch_size=10, flush_interval_ms=100)
