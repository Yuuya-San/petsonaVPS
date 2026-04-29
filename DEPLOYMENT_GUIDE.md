# Production Deployment Guide

## Pre-Deployment Security Checklist

### 1. Environment Variables (.env)
- [x] Never commit `.env` to version control
- [x] Use `.env.example` as a template
- [x] All secrets must come from environment variables

**Required environment variables:**

```bash
# Core Configuration
SECRET_KEY=<generate-strong-random-key>
DATABASE_URI=mysql+pymysql://username:password@db-host/petsona
FLASK_ENV=production

# Email Configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password  # Use app-specific passwords for Gmail
MAIL_DEFAULT_SENDER=noreply@yourdomain.com

# Google OAuth (get from Google Cloud Console)
GOOGLE_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<your-client-secret>

# Optional Security
MAX_FAILED_LOGIN=5
LOCKOUT_TIME=300
RESET_TOKEN_EXPIRY=3600
FRONTEND_URL=https://yourdomain.com
```

### 2. Generate Strong SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Database Setup

- Use a dedicated database user (not `root`)
- Set strong password
- Restrict database access by IP
- Enable database backups

Example:
```sql
CREATE USER 'petsona_user'@'localhost' IDENTIFIED BY 'very_strong_password';
GRANT ALL PRIVILEGES ON petsona.* TO 'petsona_user'@'localhost';
FLUSH PRIVILEGES;
```

### 4. Web Server Setup (Gunicorn + Nginx)

#### Install Gunicorn
```bash
pip install gunicorn eventlet
```

#### Systemd Service File (`/etc/systemd/system/petsona.service`)
```ini
[Unit]
Description=Petsona Flask App
After=network.target

[Service]
User=petsona
WorkingDirectory=/path/to/petsona
Environment="PATH=/path/to/petsona/venv/bin"
ExecStart=/path/to/petsona/venv/bin/gunicorn \
    --worker-class eventlet \
    -w 1 \
    --bind 127.0.0.1:5000 \
    --access-logfile /var/log/petsona/access.log \
    --error-logfile /var/log/petsona/error.log \
    'run:app'

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable petsona
sudo systemctl start petsona
```

#### Nginx Configuration
```nginx
upstream petsona {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL Configuration (use Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # Security headers
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    client_max_body_size 20M;

    location / {
        proxy_pass http://petsona;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /socket.io {
        proxy_pass http://petsona/socket.io;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /path/to/petsona/app/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

### 5. SSL/TLS Certificate

Use Let's Encrypt:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d yourdomain.com -d www.yourdomain.com
```

### 6. Database Backups

Create a backup script (`/usr/local/bin/backup-petsona.sh`):
```bash
#!/bin/bash
BACKUP_DIR="/backups/petsona"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/petsona_$DATE.sql"

mkdir -p "$BACKUP_DIR"
mysqldump -u petsona_user -p"$DB_PASSWORD" petsona > "$BACKUP_FILE"
gzip "$BACKUP_FILE"

# Keep only last 30 days
find "$BACKUP_DIR" -name "*.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_FILE.gz"
```

Add to crontab:
```bash
0 2 * * * /usr/local/bin/backup-petsona.sh
```

### 7. Monitoring & Logging

Monitor with systemd:
```bash
sudo journalctl -u petsona -f
```

Check application logs:
```bash
tail -f /var/log/petsona/error.log
tail -f /var/log/petsona/access.log
```

### 8. Firewall Configuration

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

### 9. Production Checklist

- [ ] `SECRET_KEY` is strong and random
- [ ] `FLASK_ENV=production` is set
- [ ] All database credentials are from environment variables
- [ ] All OAuth secrets are from environment variables
- [ ] SSL/TLS certificates installed (Let's Encrypt)
- [ ] HTTPS enforced (redirect HTTP to HTTPS)
- [ ] Gunicorn configured as systemd service
- [ ] Nginx reverse proxy configured
- [ ] Database user has restricted privileges
- [ ] Database backups automated
- [ ] Error logs monitored
- [ ] Firewall configured
- [ ] Email credentials use app-specific passwords
- [ ] Admin password changed from default
- [ ] DEBUG and TESTING modes disabled

### 10. Health Checks

After deployment:

```bash
# Check app is running
curl -I https://yourdomain.com/

# Check WebSocket (if available)
curl -I https://yourdomain.com/socket.io

# Check database connection
# (Navigate to app and test database-dependent features)

# Monitor service
sudo systemctl status petsona
```

## Key Security Changes Made

1. ✅ **Removed hardcoded credentials** - All secrets now come from environment variables
2. ✅ **Enforced environment variable validation** - App won't start without required env vars
3. ✅ **Production config** - Disables debug, enforces HTTPS cookies, disables insecure transport
4. ✅ **Development config** - Separate relaxed settings for local development
5. ✅ **Updated entry point** - `run.py` detects production and warns about using Gunicorn
6. ✅ **Created .env.example** - Template for required environment variables

## Troubleshooting

### "Missing required environment variable"
- Check `.env` file exists and has all required variables
- Run: `env | grep FLASK_ENV` to verify environment is set

### OAuth not working
- Verify `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are correct
- In production, `AUTHLIB_INSECURE_TRANSPORT` is False (no HTTPS not allowed)
- Ensure redirect URIs are configured in Google Cloud Console

### Email not sending
- Use Gmail app-specific passwords, not regular password
- Verify SMTP credentials in `.env`
- Check firewall allows outbound SMTP (port 587)

### Database connection errors
- Verify `DATABASE_URI` format: `mysql+pymysql://user:password@host/dbname`
- Check database server is running and accessible
- Verify user has correct permissions
