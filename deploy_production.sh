#!/bin/bash
# Production Deployment Script for Petsona Socket.IO
# Ensures all optimizations are in place and system is production-ready

set -e

echo "🚀 Petsona Socket.IO Production Deployment Setup"
echo "=================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Install dependencies
echo -e "${BLUE}[1/6]${NC} Installing dependencies..."
if ! pip install -r requirements.txt > /dev/null 2>&1; then
    echo -e "${RED}❌ Failed to install requirements${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Step 2: Verify eventlet installation
echo -e "${BLUE}[2/6]${NC} Verifying eventlet installation..."
if python -c "import eventlet" 2>/dev/null; then
    EVENTLET_VERSION=$(python -c "import eventlet; print(eventlet.__version__)")
    echo -e "${GREEN}✅ Eventlet ${EVENTLET_VERSION} installed${NC}"
else
    echo -e "${RED}❌ Eventlet not installed${NC}"
    exit 1
fi
echo ""

# Step 3: Check Redis (optional)
echo -e "${BLUE}[3/6]${NC} Checking Redis (optional)..."
if python -c "import redis" 2>/dev/null; then
    echo -e "${GREEN}✅ Redis Python client installed${NC}"
    
    # Try to connect to Redis
    if python -c "import redis; redis.Redis().ping()" 2>/dev/null; then
        echo -e "${GREEN}✅ Redis server is running${NC}"
    else
        echo -e "${YELLOW}⚠️  Redis server not running (optional)${NC}"
        echo "   To enable distributed deployments:"
        echo "   - Install Redis: sudo apt-get install redis-server"
        echo "   - Or Docker: docker run -d -p 6379:6379 redis:latest"
    fi
else
    echo -e "${YELLOW}⚠️  Redis Python client not installed (optional)${NC}"
fi
echo ""

# Step 4: Verify Socket.IO optimizations
echo -e "${BLUE}[4/6]${NC} Verifying Socket.IO optimizations..."

# Check if eventlet is configured
if grep -q "async_mode='eventlet'" app/extensions.py; then
    echo -e "${GREEN}✅ Eventlet async mode configured${NC}"
else
    echo -e "${RED}❌ Eventlet not configured in extensions.py${NC}"
    exit 1
fi

# Check if WebSocket transport only
if grep -q "transports=\['websocket'\]" app/extensions.py; then
    echo -e "${GREEN}✅ WebSocket transport only (no polling)${NC}"
else
    echo -e "${RED}❌ WebSocket transport not configured${NC}"
    exit 1
fi

# Check if compression enabled
if grep -q "compress=True" app/extensions.py; then
    echo -e "${GREEN}✅ Message compression enabled${NC}"
else
    echo -e "${RED}❌ Message compression not enabled${NC}"
    exit 1
fi
echo ""

# Step 5: Verify rate limiting
echo -e "${BLUE}[5/6]${NC} Verifying rate limiting..."
if grep -q "socket_rate_limiter = SocketEventRateLimiter" app/socket_utils.py; then
    echo -e "${GREEN}✅ Rate limiter configured${NC}"
else
    echo -e "${RED}❌ Rate limiter not configured${NC}"
    exit 1
fi
echo ""

# Step 6: Configuration check
echo -e "${BLUE}[6/6]${NC} Configuration check..."

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo "Creating default .env for production..."
    cat > .env << EOF
# Flask Environment
FLASK_ENV=production

# Server Settings
HOST=0.0.0.0
PORT=5000

# Database (Update with your settings)
DATABASE_URI=mysql+pymysql://user:password@localhost:3306/petsona

# Redis (Optional)
REDIS_URL=redis://localhost:6379/0
SOCKETIO_USE_REDIS=true
SOCKETIO_REDIS_URL=redis://localhost:6379/1
EOF
    echo -e "${GREEN}✅ .env file created (update with your settings)${NC}"
else
    echo -e "${GREEN}✅ .env file exists${NC}"
fi
echo ""

# Summary
echo "=================================================="
echo -e "${GREEN}🎉 All production checks passed!${NC}"
echo "=================================================="
echo ""
echo "📊 System Configuration:"
echo "  - Async Mode: eventlet (greenlet-based)"
echo "  - Transport: WebSocket only (no polling)"
echo "  - Compression: Enabled (gzip)"
echo "  - Rate Limiting: 10 events/sec per client"
echo "  - Connection Pool: Managed"
echo "  - Event Deduplication: Enabled (60s TTL)"
echo ""
echo "🚀 To start production server:"
echo "   export FLASK_ENV=production"
echo "   python run.py"
echo ""
echo "   Or with Gunicorn:"
echo "   gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 run:app"
echo ""
echo "📈 To monitor performance:"
echo "   curl http://localhost:5000/socket/metrics | jq"
echo "   curl http://localhost:5000/socket/health | jq"
echo "   curl http://localhost:5000/socket/performance | jq"
echo ""
echo "📚 Full documentation in: SOCKETIO_PRODUCTION_GUIDE.md"
echo ""
