#!/bin/bash

# MeatLizard AI Platform Production Deployment Script
# This script sets up the complete production environment

set -e

echo "🦎 MeatLizard AI Platform - Production Deployment"
echo "=================================================="


# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

# Load environment variables
source .env

# Validate required environment variables
required_vars=(
    "DISCORD_BOT_TOKEN"
    "DISCORD_CLIENT_BOT_TOKEN"
    "DISCORD_GUILD_ID"
    "PAYLOAD_ENCRYPTION_KEY"
    "SECRET_KEY"
    "JWT_SECRET_KEY"
)

echo "🔍 Validating environment configuration..."
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Required environment variable $var is not set"
        exit 1
    fi
done
echo "✅ Environment validation passed"

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs media/uploads media/transcoded media/thumbnails
mkdir -p /tmp/transcoding /tmp/imports
echo "✅ Directories created"

# Generate encryption key if not provided
if [ -z "$PAYLOAD_ENCRYPTION_KEY" ]; then
    echo "🔐 Generating encryption key..."
    PAYLOAD_ENCRYPTION_KEY=$(python3 -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())")
    echo "PAYLOAD_ENCRYPTION_KEY=$PAYLOAD_ENCRYPTION_KEY" >> .env
    echo "✅ Encryption key generated and added to .env"
fi

# Install system dependencies
echo "📦 Installing system dependencies..."
if command -v apt-get &> /dev/null; then
    # Ubuntu/Debian
    sudo apt-get update
    sudo apt-get install -y \
        docker.io docker-compose \
        nginx certbot python3-certbot-nginx \
        ffmpeg yt-dlp \
        postgresql-client redis-tools \
        curl wget git
elif command -v yum &> /dev/null; then
    # CentOS/RHEL
    sudo yum update -y
    sudo yum install -y \
        docker docker-compose \
        nginx certbot python3-certbot-nginx \
        ffmpeg yt-dlp \
        postgresql redis \
        curl wget git
elif command -v brew &> /dev/null; then
    # macOS
    brew install docker docker-compose nginx ffmpeg yt-dlp postgresql redis
else
    echo "⚠️  Could not detect package manager. Please install dependencies manually:"
    echo "   - Docker & Docker Compose"
    echo "   - Nginx"
    echo "   - FFmpeg"
    echo "   - yt-dlp"
    echo "   - PostgreSQL client"
    echo "   - Redis tools"
fi

# Start Docker service
echo "🐳 Starting Docker service..."
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
echo "✅ Docker service started"

# Build and start services
echo "🏗️  Building and starting services..."
docker-compose down --remove-orphans
docker-compose build --no-cache
docker-compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 30

# Check service health
services=("postgres" "redis" "web")
for service in "${services[@]}"; do
    echo "🔍 Checking $service health..."
    if docker-compose ps $service | grep -q "healthy\|Up"; then
        echo "✅ $service is healthy"
    else
        echo "❌ $service is not healthy"
        docker-compose logs $service
        exit 1
    fi
done

# Run database migrations
echo "🗄️  Running database migrations..."
docker-compose exec web alembic upgrade head
echo "✅ Database migrations completed"

# Setup SSL certificates (if domain is configured)
if [ ! -z "$DOMAIN" ] && [ "$DOMAIN" != "localhost:8000" ]; then
    echo "🔒 Setting up SSL certificates for $DOMAIN..."
    sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email $ADMIN_EMAIL
    echo "✅ SSL certificates configured"
fi

# Create admin user (optional)
read -p "🔑 Create admin user? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Admin username: " admin_username
    read -s -p "Admin password: " admin_password
    echo
    
    docker-compose exec web python -c "
import asyncio
from server.web.app.api.auth import hash_password
from server.web.app.models import User, UserTier, UserTierEnum
from server.web.app.db import get_async_session
import uuid

async def create_admin():
    async with get_async_session() as db:
        admin = User(
            id=uuid.uuid4(),
            display_label='$admin_username',
            password_hash=hash_password('$admin_password'),
            email='$ADMIN_EMAIL',
            is_active=True
        )
        db.add(admin)
        
        tier = UserTier(
            user_id=admin.id,
            tier=UserTierEnum.business
        )
        db.add(tier)
        
        await db.commit()
        print('Admin user created successfully')

asyncio.run(create_admin())
"
    echo "✅ Admin user created"
fi

# Display deployment summary
echo ""
echo "🎉 MeatLizard AI Platform deployed successfully!"
echo "=============================================="
echo ""
echo "🌐 Web Interface: http://${DOMAIN:-localhost:8000}"
echo "📊 Monitoring: http://${DOMAIN:-localhost}:3000 (Grafana)"
echo "📈 Metrics: http://${DOMAIN:-localhost}:9090 (Prometheus)"
echo ""
echo "📋 Service Status:"
docker-compose ps
echo ""
echo "📝 Next Steps:"
echo "1. Configure your Discord bots in the Discord Developer Portal"
echo "2. Set up your S3 storage bucket and configure credentials"
echo "3. Configure email settings for notifications"
echo "4. Set up monitoring alerts in Grafana"
echo "5. Configure your client bot on macOS with Apple Silicon"
echo ""
echo "📚 Documentation: Check the docs/ directory for detailed guides"
echo ""
echo "🔧 Useful Commands:"
echo "  - View logs: docker-compose logs -f [service]"
echo "  - Restart service: docker-compose restart [service]"
echo "  - Update deployment: docker-compose pull && docker-compose up -d"
echo "  - Backup database: scripts/backup-database.sh"
echo ""

# Setup log rotation
echo "📋 Setting up log rotation..."
sudo tee /etc/logrotate.d/meatlizard > /dev/null <<EOF
$(pwd)/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $(whoami) $(whoami)
    postrotate
        docker-compose restart web server_bot transcoding_worker import_worker
    endscript
}
EOF
echo "✅ Log rotation configured"

# Setup systemd service for auto-start
echo "🔄 Setting up systemd service..."
sudo tee /etc/systemd/system/meatlizard.service > /dev/null <<EOF
[Unit]
Description=MeatLizard AI Platform
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable meatlizard.service
echo "✅ Systemd service configured"

echo ""
echo "🎊 Deployment completed successfully!"
echo "Your MeatLizard AI Platform is now running in production mode."