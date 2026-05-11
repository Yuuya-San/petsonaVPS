#!/bin/bash
# Flask Session Persistence Validation Script
# Run this after applying the fixes to verify everything works

set -e

echo "🔍 Flask Session Persistence Validation"
echo "======================================"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to check if service is running
check_service() {
    local service=$1
    if systemctl is-active --quiet "$service" 2>/dev/null; then
        echo -e "${GREEN}✅ $service is running${NC}"
        return 0
    else
        echo -e "${RED}❌ $service is not running${NC}"
        return 1
    fi
}

# Function to test HTTP endpoint
test_endpoint() {
    local url=$1
    local expected_code=$2
    local description=$3

    if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "$expected_code"; then
        echo -e "${GREEN}✅ $description${NC}"
        return 0
    else
        echo -e "${RED}❌ $description failed${NC}"
        return 1
    fi
}

echo ""
echo "1. Checking services..."
check_service nginx || echo "   Run: sudo systemctl start nginx"
check_service petsona || echo "   Run: sudo systemctl start petsona"

echo ""
echo "2. Testing application health..."
test_endpoint "http://localhost/" "200" "Application homepage accessible"
test_endpoint "https://your-domain.com/" "200" "HTTPS redirect working"

echo ""
echo "3. Testing session configuration..."
# Test the debug endpoint (remove this route in production!)
test_endpoint "https://your-domain.com/auth/debug/session" "200" "Session debug endpoint"

echo ""
echo "4. Manual testing steps:"
echo "   a) Visit: https://your-domain.com/auth/admin-login"
echo "   b) Login with admin credentials"
echo "   c) Check browser developer tools -> Application -> Cookies"
echo "   d) Verify 'session' cookie exists and is secure"
echo "   e) Check logs for session debug messages"
echo "   f) Verify redirect to admin dashboard works"

echo ""
echo "5. Log verification:"
echo "   Check application logs:"
echo "   sudo journalctl -u petsona -f"
echo ""
echo "   Look for these log messages after login:"
echo "   - 'User X logged in successfully. current_user.is_authenticated: True'"
echo "   - 'Session keys after login: [...]'"
echo "   - 'Session cookie name: session'"

echo ""
echo "6. Browser cookie verification:"
echo "   Open browser dev tools -> Network tab"
echo "   Perform login and check response headers for 'Set-Cookie'"
echo "   Verify cookie attributes: Secure, HttpOnly, SameSite=Lax"

echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: Remove the debug route /auth/debug/session before going live!${NC}"
echo ""
echo "7. Production cleanup:"
echo "   - Remove /auth/debug/session route from routes.py"
echo "   - Remove debug logging from admin_login function"
echo "   - Ensure SECRET_KEY is properly set in environment"
echo "   - Test with real domain and SSL certificate"