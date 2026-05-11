"""
Socket.IO Monitoring and Debugging Utilities
Production-ready monitoring for Socket.IO performance and connection health
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
from collections import defaultdict
import time

logger = logging.getLogger(__name__)


class SocketMetrics:
    """
    Tracks Socket.IO metrics for monitoring and debugging
    Helps identify performance issues and connection problems
    """
    
    def __init__(self):
        self.metrics = {
            'connections': defaultdict(int),  # event_type -> count
            'disconnections': defaultdict(int),
            'events': defaultdict(int),  # event_name -> count
            'errors': defaultdict(int),  # error_type -> count
            'start_time': datetime.now(),
            'event_times': defaultdict(list),  # event_name -> [times]
        }
    
    def record_connection(self, user_id: int = None, anonymous: bool = False):
        """Record a new connection"""
        key = 'authenticated' if user_id else 'anonymous'
        self.metrics['connections'][key] += 1
        logger.debug(f"Connection recorded: {key} (total: {self.metrics['connections'][key]})")
    
    def record_disconnection(self, user_id: int = None):
        """Record a disconnection"""
        key = 'authenticated' if user_id else 'anonymous'
        self.metrics['disconnections'][key] += 1
    
    def record_event(self, event_name: str, duration_ms: float = None):
        """
        Record an event emission/handling
        
        Args:
            event_name: Name of the event
            duration_ms: Time taken to process event (optional)
        """
        self.metrics['events'][event_name] += 1
        
        if duration_ms is not None:
            self.metrics['event_times'][event_name].append(duration_ms)
    
    def record_error(self, error_type: str):
        """Record an error"""
        self.metrics['errors'][error_type] += 1
        logger.warning(f"Socket error recorded: {error_type}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of metrics"""
        uptime = datetime.now() - self.metrics['start_time']
        
        # Calculate average event handling times
        avg_event_times = {}
        for event_name, times in self.metrics['event_times'].items():
            if times:
                avg_event_times[event_name] = {
                    'avg_ms': sum(times) / len(times),
                    'min_ms': min(times),
                    'max_ms': max(times),
                    'samples': len(times)
                }
        
        return {
            'uptime_seconds': uptime.total_seconds(),
            'connections': dict(self.metrics['connections']),
            'disconnections': dict(self.metrics['disconnections']),
            'total_events': sum(self.metrics['events'].values()),
            'events_by_type': dict(self.metrics['events']),
            'errors': dict(self.metrics['errors']),
            'event_timings': avg_event_times,
            'start_time': self.metrics['start_time'].isoformat()
        }
    
    def reset(self):
        """Reset all metrics"""
        for key in self.metrics:
            if key != 'start_time':
                if isinstance(self.metrics[key], dict):
                    self.metrics[key].clear()
        self.metrics['start_time'] = datetime.now()
        logger.info("Socket metrics reset")


class SocketHealthCheck:
    """
    Health check utility for Socket.IO connections
    Monitors connection quality and identifies stale connections
    """
    
    def __init__(self, max_idle_seconds: int = 300):
        self.max_idle_seconds = max_idle_seconds
        self.connections = {}  # sid -> {'user_id', 'connected_at', 'last_activity'}
    
    def add_connection(self, sid: str, user_id: int = None):
        """Register a new connection"""
        self.connections[sid] = {
            'user_id': user_id,
            'connected_at': datetime.now(),
            'last_activity': datetime.now(),
            'events_received': 0,
            'events_sent': 0
        }
    
    def remove_connection(self, sid: str):
        """Unregister a connection"""
        if sid in self.connections:
            duration = datetime.now() - self.connections[sid]['connected_at']
            logger.debug(f"Connection removed: {sid} (duration: {duration.total_seconds():.1f}s)")
            del self.connections[sid]
    
    def record_activity(self, sid: str):
        """Update last activity for a connection"""
        if sid in self.connections:
            self.connections[sid]['last_activity'] = datetime.now()
            self.connections[sid]['events_received'] += 1
    
    def get_idle_connections(self) -> List[str]:
        """Get list of idle (stale) connections"""
        now = datetime.now()
        idle = []
        
        for sid, conn in self.connections.items():
            idle_time = (now - conn['last_activity']).total_seconds()
            if idle_time > self.max_idle_seconds:
                idle.append(sid)
        
        return idle
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get connection health status"""
        now = datetime.now()
        idle_connections = self.get_idle_connections()
        
        total_duration = 0
        for conn in self.connections.values():
            total_duration += (now - conn['connected_at']).total_seconds()
        
        avg_duration = (
            total_duration / len(self.connections) 
            if self.connections else 0
        )
        
        return {
            'total_connections': len(self.connections),
            'idle_connections': len(idle_connections),
            'average_connection_duration_seconds': avg_duration,
            'status': 'healthy' if len(idle_connections) == 0 else 'degraded'
        }


class SocketDebugger:
    """
    Debugging utility for Socket.IO event flow and performance analysis
    """
    
    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.event_log = []
        self.max_log_size = 1000
    
    def log_event(self, event_name: str, data: Dict = None, direction: str = 'in'):
        """
        Log an event for debugging
        
        Args:
            event_name: Name of the event
            data: Event data (truncated for logging)
            direction: 'in' or 'out' for incoming/outgoing
        """
        if not self.enabled:
            return
        
        # Truncate data for logging
        truncated_data = None
        if data:
            data_str = str(data)[:100]  # First 100 chars
            truncated_data = data_str + ('...' if len(str(data)) > 100 else '')
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'event': event_name,
            'data': truncated_data,
            'direction': direction
        }
        
        self.event_log.append(entry)
        
        # Keep log size manageable
        if len(self.event_log) > self.max_log_size:
            self.event_log = self.event_log[-self.max_log_size:]
        
        logger.debug(f"[{direction}] {event_name}: {truncated_data}")
    
    def get_event_log(self, limit: int = 100) -> List[Dict]:
        """Get recent event log entries"""
        return self.event_log[-limit:]
    
    def clear_log(self):
        """Clear event log"""
        self.event_log = []
    
    def get_event_summary(self) -> Dict[str, int]:
        """Get summary of events in log"""
        summary = defaultdict(int)
        for entry in self.event_log:
            summary[entry['event']] += 1
        return dict(summary)


class PerformanceMonitor:
    """
    Monitors Socket.IO performance metrics
    Helps identify bottlenecks and optimization opportunities
    """
    
    def __init__(self):
        self.timings = defaultdict(list)  # event_name -> [durations]
        self.start_times = {}  # event_id -> start_time
    
    def start_timer(self, event_id: str):
        """Start timing an event"""
        self.start_times[event_id] = time.time()
    
    def end_timer(self, event_id: str, event_name: str = None) -> float:
        """
        End timing an event and record duration
        
        Returns:
            Duration in milliseconds
        """
        if event_id not in self.start_times:
            return 0
        
        duration_ms = (time.time() - self.start_times[event_id]) * 1000
        del self.start_times[event_id]
        
        if event_name:
            self.timings[event_name].append(duration_ms)
        
        return duration_ms
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get performance report for all events"""
        report = {}
        
        for event_name, durations in self.timings.items():
            if durations:
                sorted_durations = sorted(durations)
                report[event_name] = {
                    'count': len(durations),
                    'avg_ms': sum(durations) / len(durations),
                    'min_ms': min(durations),
                    'max_ms': max(durations),
                    'p95_ms': sorted_durations[int(len(durations) * 0.95)] if durations else 0,
                    'p99_ms': sorted_durations[int(len(durations) * 0.99)] if durations else 0,
                }
        
        return report
    
    def reset(self):
        """Reset all performance data"""
        self.timings.clear()
        self.start_times.clear()


# ==================== GLOBAL INSTANCES ====================

socket_metrics = SocketMetrics()
socket_health = SocketHealthCheck(max_idle_seconds=300)
socket_debugger = SocketDebugger(enabled=False)  # Enable via config if needed
performance_monitor = PerformanceMonitor()


# ==================== MONITORING ROUTES (Optional Flask route) ====================

def create_monitoring_blueprint(app):
    """
    Create a Flask blueprint for Socket.IO monitoring endpoints
    
    Usage:
        from app.socket_monitoring import create_monitoring_blueprint
        monitoring_bp = create_monitoring_blueprint(app)
        app.register_blueprint(monitoring_bp)
    
    Then access:
        GET /socket/metrics - Get metrics summary
        GET /socket/health - Get health check
        GET /socket/debug/events - Get event log
    """
    from flask import Blueprint, jsonify
    
    monitoring_bp = Blueprint('socket_monitoring', __name__, url_prefix='/socket')
    
    @monitoring_bp.route('/metrics', methods=['GET'])
    def get_metrics():
        """Get Socket.IO metrics"""
        return jsonify(socket_metrics.get_summary())
    
    @monitoring_bp.route('/health', methods=['GET'])
    def get_health():
        """Get Socket.IO health status"""
        return jsonify(socket_health.get_health_status())
    
    @monitoring_bp.route('/performance', methods=['GET'])
    def get_performance():
        """Get performance metrics"""
        return jsonify(performance_monitor.get_performance_report())
    
    @monitoring_bp.route('/debug/events', methods=['GET'])
    def get_debug_events():
        """Get debug event log (limited)"""
        if not socket_debugger.enabled:
            return jsonify({'error': 'Debug mode not enabled'}), 403
        
        return jsonify({
            'events': socket_debugger.get_event_log(100),
            'summary': socket_debugger.get_event_summary()
        })
    
    @monitoring_bp.route('/debug/enable', methods=['POST'])
    def enable_debug():
        """Enable debug mode"""
        socket_debugger.enabled = True
        logger.info("Socket.IO debug mode enabled")
        return jsonify({'status': 'debug mode enabled'})
    
    @monitoring_bp.route('/debug/disable', methods=['POST'])
    def disable_debug():
        """Disable debug mode"""
        socket_debugger.enabled = False
        socket_debugger.clear_log()
        logger.info("Socket.IO debug mode disabled")
        return jsonify({'status': 'debug mode disabled'})
    
    return monitoring_bp
