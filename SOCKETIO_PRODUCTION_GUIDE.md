# Socket.IO Production Deployment Guide

## Overview

This guide covers production-ready Socket.IO deployment with eventlet, optimizations to prevent unnecessary requests, and performance monitoring.

---

## 1. Production Architecture

### Technology Stack

- **Async Mode**: Eventlet (greenlet-based async I/O)
- **Transport**: WebSocket only (no polling to reduce unnecessary requests)
- **Message Queue**: Redis (for distributed deployments)
- **Rate Limiting**: Per-client token bucket algorithm
- **Compression**: gzip message compression enabled

### Key Optimizations

✅ **Eventlet** - High-performance greenlet-based async I/O
✅ **WebSocket Only** - Disabled polling to eliminate unnecessary requests
✅ **Message Compression** - Gzip compression on all messages
✅ **Rate Limiting** - Per-client rate limiter (10 events/sec default, 2-5 for typing)
✅ **Event Deduplication** - Prevents duplicate broadcasts
✅ **Connection Pooling** - Tracks and manages active connections
✅ **Event Batching** - Groups high-frequency events
✅ **Request Deduplication** - Client-side deduplication prevents redundant emissions

---

## 2. Installation

### Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages added:
- `eventlet>=0.33.3` - High-performance async server
- `python-socketio[client]>=5.9.0` - SocketIO client support
- `redis>=4.5.0` - Optional, for distributed deployments
- `greenlet>=2.0.0` - Lightweight concurrency

---

## 3. Configuration

### Environment Variables

Create `.env` file with:

```bash
# Flask environment
FLASK_ENV=production

# Server settings
HOST=0.0.0.0
PORT=5000

# Redis (optional, for distributed deployments)
REDIS_URL=redis://localhost:6379/0

# Socket.IO settings
SOCKETIO_USE_REDIS=true
SOCKETIO_REDIS_URL=redis://localhost:6379/1

# Database
DATABASE_URI=mysql+pymysql://user:password@host:3306/petsona
```

### Socket.IO Configuration (`app/extensions.py`)

```python
socketio = SocketIO(
    async_mode='eventlet',  # High-performance greenlet mode
    cors_allowed_origins="*",
    ping_timeout=120,        # Disconnect idle clients after 120s
    ping_interval=30,        # Server ping every 30s
    transports=['websocket'], # WebSocket only (no polling)
    compress=True,           # Enable gzip compression
    manage_acks=True,        # Track message acknowledgments
)
```

### Rate Limiting Configuration

Default rate limits per client:
- **General events**: 10 per second (50 token burst)
- **Typing events**: 2 per second
- **Status events**: 1 per second
- **Watch species**: 10 per second

Configure in `app/socket_utils.py`:

```python
socket_rate_limiter = SocketEventRateLimiter(
    max_events_per_second=10.0,
    bucket_capacity=50
)
```

---

## 4. Running the Server

### Development Mode

```bash
export FLASK_ENV=development
python run.py
```

Uses threading-based async mode (easier to debug)

### Production Mode with Eventlet

```bash
export FLASK_ENV=production
python run.py
```

Automatically uses eventlet for high-performance async I/O

### Production with Gunicorn + Eventlet

For better process management:

```bash
pip install gunicorn
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 run:app
```

### Production with Multiple Workers

```bash
gunicorn \
  --worker-class eventlet \
  -w 4 \
  --worker-connections 1000 \
  --bind 0.0.0.0:5000 \
  --access-logfile - \
  --error-logfile - \
  run:app
```

---

## 5. Redis Setup (Optional)

For distributed deployments across multiple servers:

### Install and Start Redis

```bash
# Install Redis
sudo apt-get install redis-server

# Start Redis
redis-server

# Or with Docker
docker run -d -p 6379:6379 redis:latest
```

### Enable Redis for Socket.IO

Update configuration:

```python
# app/__init__.py
socketio.init_app(
    app,
    message_queue='redis://localhost:6379/1'
)
```

This allows Socket.IO broadcasts to reach all connected clients across all server instances.

---

## 6. Nginx Configuration

### Reverse Proxy Setup

```nginx
upstream petsona_app {
    server localhost:5000;
}

server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # Compression
    gzip on;
    gzip_types text/plain application/json;
    gzip_min_length 1000;
    
    # Socket.IO configuration
    location /socket.io {
        proxy_pass http://petsona_app/socket.io;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Regular application traffic
    location / {
        proxy_pass http://petsona_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Static files
    location /static {
        alias /path/to/app/static;
        expires 30d;
    }
}
```

---

## 7. Performance Optimization Tips

### 1. Monitor Connection Health

Enable monitoring endpoints:

```python
# app/__init__.py
from app.socket_monitoring import create_monitoring_blueprint

monitoring_bp = create_monitoring_blueprint(app)
app.register_blueprint(monitoring_bp)
```

Access monitoring endpoints:
- `GET /socket/metrics` - Event counts and statistics
- `GET /socket/health` - Connection health status
- `GET /socket/performance` - Event timing statistics

### 2. Debug Mode

Enable debug logging:

```bash
# Via HTTP
curl -X POST http://localhost:5000/socket/debug/enable

# Or set in code
from app.socket_monitoring import socket_debugger
socket_debugger.enabled = True
```

View debug events:
```bash
curl http://localhost:5000/socket/debug/events | jq
```

### 3. Tuning Rate Limits

Adjust based on your use case in `app/socket_utils.py`:

```python
# More restrictive (for low-bandwidth scenarios)
socket_rate_limiter = SocketEventRateLimiter(
    max_events_per_second=5.0,
    bucket_capacity=25
)

# More permissive (for high-frequency updates)
socket_rate_limiter = SocketEventRateLimiter(
    max_events_per_second=20.0,
    bucket_capacity=100
)
```

### 4. Connection Pool Management

Monitor idle connections:

```python
from app.socket_utils import socket_connection_pool

stats = socket_connection_pool.get_stats()
print(f"Total connections: {stats['total_connections']}")
print(f"Users connected: {stats['total_users']}")
```

### 5. Reduce Unnecessary Polling

All optimizations are enabled by default:
- ✅ WebSocket transport only (no polling)
- ✅ Client-side deduplication
- ✅ Event batching for high-frequency events
- ✅ Server-side deduplication

---

## 8. Client-Side Optimization

### JavaScript Socket Manager Features

```javascript
// Connection with optimizations enabled
const socketManager = new SocketManager();

// Check connection status
console.log(socketManager.isConnected());

// Get statistics
const stats = window.getSocketStats();
console.log(stats);
// {
//   connected: true,
//   watchers: 5,
//   reconnectAttempts: 0,
//   pendingBatches: 0,
//   recentEmits: 0
// }

// Manually watch species
socketManager.watchSpecies(123, (voteCount) => {
    console.log(`Species 123: ${voteCount} votes`);
});

// Unwatch when done
socketManager.unwatchSpecies(123);

// Batch event emission (high-frequency events are automatically batched)
socketManager.emitTyping(conversationId);
socketManager.emitStopTyping(conversationId);
```

### Event Listeners

```javascript
// Listen for server events
window.addEventListener('socket-ready', (e) => {
    console.log('Socket connected:', e.detail);
});

window.addEventListener('vote-update', (e) => {
    console.log('Vote update:', e.detail);
});

window.addEventListener('user-status-changed', (e) => {
    console.log('User status:', e.detail);
});

window.addEventListener('socket-new-message', (e) => {
    console.log('New message:', e.detail);
});
```

---

## 9. Monitoring and Troubleshooting

### Check Server Logs

```bash
# View Socket.IO events
tail -f /var/log/petsona/socketio.log
```

### Performance Metrics API

```bash
# Get all metrics
curl http://localhost:5000/socket/metrics | jq

# Example response:
{
  "uptime_seconds": 3600,
  "connections": {"authenticated": 45, "anonymous": 12},
  "disconnections": {"authenticated": 5},
  "total_events": 15420,
  "errors": {"rate_limit_exceeded": 2}
}
```

### Health Check API

```bash
# Check connection health
curl http://localhost:5000/socket/health | jq

# Example response:
{
  "total_connections": 57,
  "idle_connections": 0,
  "average_connection_duration_seconds": 1245,
  "status": "healthy"
}
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| High connection drop rate | Polling enabled/Network issues | Ensure `transports=['websocket']` only |
| Slow message delivery | Rate limiting too strict | Adjust bucket capacity in `socket_utils.py` |
| Memory leaks | Idle connections not cleaned | Enable idle connection cleanup |
| Duplicate events | Client deduplication not working | Check `socket-manager.js` deduplication TTL |
| Cross-instance broadcasts not working | Redis not connected | Enable Redis with `SOCKETIO_USE_REDIS=true` |

---

## 10. Security Considerations

### Enable HTTPS/WSS

Always use WSS (WebSocket Secure) in production:

```nginx
# Nginx already handles TLS termination
# WebSocket will automatically use WSS
```

### CORS Configuration

```python
socketio = SocketIO(
    cors_allowed_origins=[
        "https://your-domain.com",
        "https://www.your-domain.com"
    ]
)
```

### Rate Limiting

Protected by default with per-client token bucket:
- Prevents brute force attacks
- Prevents resource exhaustion
- Automatically logged when exceeded

### Authentication

- All socket handlers check `current_user.is_authenticated`
- Session-based authentication required for sensitive events
- Broadcasts scoped to appropriate rooms

---

## 11. Deployment Checklist

- [ ] ✅ Install eventlet, redis, and dependencies
- [ ] ✅ Configure `.env` with production settings
- [ ] ✅ Set `FLASK_ENV=production`
- [ ] ✅ Enable HTTPS/WSS in Nginx
- [ ] ✅ Setup Redis for distributed deployments
- [ ] ✅ Configure rate limiting thresholds
- [ ] ✅ Enable monitoring endpoints
- [ ] ✅ Setup log rotation
- [ ] ✅ Test failover and reconnection
- [ ] ✅ Monitor connection pool size
- [ ] ✅ Setup alerting for high error rates
- [ ] ✅ Document rate limit adjustments

---

## 12. Performance Benchmarks

Expected performance with eventlet + optimizations:

| Metric | Value |
|--------|-------|
| Concurrent connections | 1000+ per single instance |
| Event latency | < 50ms p95 |
| Message throughput | 10,000+ events/sec |
| Memory per connection | ~10-20KB |
| CPU usage | 5-15% (single core) |

---

## Support and Additional Resources

- **Flask-SocketIO Docs**: https://flask-socketio.readthedocs.io/
- **Eventlet Docs**: https://eventlet.net/
- **Socket.IO Protocol**: https://socket.io/docs/
- **Nginx WebSocket Guide**: https://nginx.org/en/docs/http/websocket.html
