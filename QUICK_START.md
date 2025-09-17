# MeatLizard AI Platform - Quick Start Guide

Get your MeatLizard AI Platform up and running in minutes!

## 🚀 Quick Deployment Options

### Option 1: Debian/Ubuntu Server (Recommended for Production)
```bash
# Clone repository
git clone <your-repository-url> meatlizard
cd meatlizard

# Run automated deployment
chmod +x scripts/deploy-production.sh
./scripts/deploy-production.sh
```

### Option 2: macOS Client Bot Only
```bash
# Clone repository
git clone <your-repository-url> meatlizard
cd meatlizard

# Run macOS client bot setup
chmod +x scripts/deploy-client-bot-macos.sh
./scripts/deploy-client-bot-macos.sh
```

## 📋 Prerequisites Checklist

Before starting, ensure you have:

### Discord Setup
- [ ] Discord Developer Account
- [ ] Two Discord bot applications created:
  - [ ] Server Bot (with Administrator permissions)
  - [ ] Client Bot (with Send Messages, Read Message History)
- [ ] Discord server/guild where both bots are invited
- [ ] Bot tokens and IDs ready

### External Services
- [ ] S3-compatible storage account (AWS S3, DigitalOcean Spaces, etc.)
- [ ] SMTP email service (Gmail, SendGrid, etc.)
- [ ] Domain name (optional, can use localhost for testing)

### System Requirements
- [ ] **Debian/Ubuntu**: 8GB RAM, 100GB storage, public IP
- [ ] **macOS**: Apple Silicon preferred, 16GB RAM, 100GB storage

## ⚡ 5-Minute Setup (Debian/Ubuntu)

### 1. Clone and Configure
```bash
git clone <your-repository-url> meatlizard
cd meatlizard
cp .env.example .env
nano .env  # Edit with your configuration
```

### 2. Essential Environment Variables
```bash
# Discord (REQUIRED)
DISCORD_BOT_TOKEN="your-server-bot-token"
DISCORD_CLIENT_BOT_TOKEN="your-client-bot-token"
DISCORD_GUILD_ID="your-discord-server-id"
DISCORD_CLIENT_BOT_ID="your-client-bot-application-id"

# Security (REQUIRED)
SECRET_KEY="your-secret-key-change-in-production"
JWT_SECRET_KEY="your-jwt-secret-key-change-in-production"

# Domain (optional)
DOMAIN="your-domain.com"  # or leave as localhost for testing
```

### 3. Deploy
```bash
chmod +x scripts/deploy-production.sh
./scripts/deploy-production.sh
```

### 4. Access Your Platform
- Web Interface: `http://your-domain.com` (or `http://localhost`)
- Create admin account when prompted
- Register users at `/register`

## 🍎 macOS Client Bot Setup

### 1. Install Dependencies
```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required packages
brew install python@3.11 cmake pkg-config git wget
```

### 2. Setup Client Bot
```bash
cd meatlizard
chmod +x scripts/deploy-client-bot-macos.sh
./scripts/deploy-client-bot-macos.sh
```

### 3. Configure and Start
```bash
cd client_bot
# Edit config.yml with your settings
nano config.yml

# Start the client bot
./run_client_bot.sh
```

## 🔧 Configuration Guide

### Discord Bot Setup
1. Go to https://discord.com/developers/applications
2. Create "MeatLizard Server Bot":
   - Bot → Reset Token → Copy token
   - Bot → Privileged Gateway Intents → Enable all
   - OAuth2 → URL Generator → Bot → Administrator → Copy URL
3. Create "MeatLizard Client Bot":
   - Same process, but only need "Send Messages" and "Read Message History"
4. Invite both bots to your Discord server
5. Get your Discord server ID (Developer Mode → Right-click server → Copy ID)

### Environment Configuration
```bash
# Required Discord settings
DISCORD_BOT_TOKEN="your-server-bot-token"
DISCORD_CLIENT_BOT_TOKEN="your-client-bot-token"
DISCORD_GUILD_ID="your-discord-server-id"
DISCORD_CLIENT_BOT_ID="your-client-bot-application-id"
DISCORD_ADMIN_ROLES="admin-role-id-1,admin-role-id-2"

# Generate encryption key
PAYLOAD_ENCRYPTION_KEY="$(python3 -c 'import base64, os; print(base64.b64encode(os.urandom(32)).decode())')"

# Security keys (generate random strings)
SECRET_KEY="$(openssl rand -base64 32)"
JWT_SECRET_KEY="$(openssl rand -base64 32)"

# Database (default works for local setup)
DATABASE_URL="postgresql+asyncpg://meatlizard:meatlizard_password@postgres:5432/meatlizard"

# Email (optional, for notifications)
SMTP_SERVER="smtp.gmail.com"
SMTP_PORT=587
SMTP_USERNAME="your-email@gmail.com"
SMTP_PASSWORD="your-app-password"
FROM_EMAIL="noreply@your-domain.com"

# S3 Storage (optional, for file uploads)
S3_BUCKET_NAME="meatlizard-storage"
S3_ACCESS_KEY_ID="your-access-key"
S3_SECRET_ACCESS_KEY="your-secret-key"
S3_REGION="us-east-1"
```

## ✅ Verification Steps

### 1. Check Services
```bash
# Check Docker services
docker-compose ps

# Check logs
docker-compose logs -f web
docker-compose logs -f server_bot

# Run status check
./scripts/status-check.sh
```

### 2. Test Web Interface
1. Visit your domain or `http://localhost`
2. Register a new account
3. Login and access dashboard
4. Test each feature (AI Chat, URL Shortener, Pastebin, etc.)

### 3. Test AI Chat
1. Go to `/chat` or click "AI Chat" in dashboard
2. Click "Connect to AI"
3. Send a test message
4. Verify response from AI model

### 4. Test Discord Integration
1. Check Discord server for bot presence
2. Look for "AI Chat Sessions" category
3. Start chat from web interface
4. Verify private channel creation

## 🚨 Troubleshooting

### Common Issues

**Docker permission denied:**
```bash
sudo usermod -aG docker $USER
# Log out and back in
```

**Database connection failed:**
```bash
docker-compose logs postgres
sudo systemctl status postgresql
```

**Discord bots not responding:**
```bash
# Check bot tokens in .env
# Verify bots are invited to server
# Check Discord API status
docker-compose logs server_bot
```

**AI Chat not working:**
```bash
# Check client bot status (macOS)
cd client_bot && ./monitor_client_bot.sh

# Verify encryption keys match
# Check model files exist
```

**Web interface not accessible:**
```bash
# Check nginx status
sudo systemctl status nginx
sudo nginx -t

# Check FastAPI logs
docker-compose logs web
```

### Quick Fixes

**Restart all services:**
```bash
docker-compose restart
```

**Rebuild and restart:**
```bash
docker-compose down
docker-compose up -d --build
```

**Reset database:**
```bash
docker-compose down -v
docker-compose up -d
docker-compose exec web alembic upgrade head
```

**Check system resources:**
```bash
df -h  # Disk space
free -h  # Memory
docker stats  # Container resources
```

## 📚 Next Steps

### Production Hardening
1. **SSL Certificate**: Set up HTTPS with Let's Encrypt
2. **Firewall**: Configure UFW or iptables
3. **Monitoring**: Set up Grafana dashboards
4. **Backups**: Configure automated database backups
5. **Updates**: Set up automatic security updates

### Feature Configuration
1. **Email Service**: Configure SMTP for notifications
2. **S3 Storage**: Set up file storage and CDN
3. **Custom Domain**: Configure DNS and SSL
4. **User Tiers**: Set up pricing and permissions
5. **Content Moderation**: Configure AI filtering

### Scaling
1. **Load Balancing**: Add multiple web servers
2. **Database Scaling**: Set up read replicas
3. **CDN**: Configure CloudFlare or similar
4. **Monitoring**: Set up alerting and metrics
5. **High Availability**: Multi-region deployment

## 🆘 Getting Help

### Documentation
- **Full Deployment**: `DEPLOYMENT_DEBIAN.md` or `DEPLOYMENT_MACOS.md`
- **Architecture**: `DEPLOYMENT.md`
- **API Reference**: Visit `/api/docs` on your instance

### Support Channels
- **Status Check**: Run `./scripts/status-check.sh`
- **Logs**: `docker-compose logs -f [service]`
- **GitHub Issues**: Report bugs and feature requests
- **Discord Community**: Join our support server

### Useful Commands
```bash
# View all logs
docker-compose logs -f

# Restart specific service
docker-compose restart web

# Update platform
git pull && docker-compose up -d --build

# Backup database
docker-compose exec postgres pg_dump -U meatlizard meatlizard > backup.sql

# Monitor resources
docker stats

# Check service health
curl http://localhost:8000/health
```

## 🎉 Success!

If you've made it this far, your MeatLizard AI Platform should be running successfully!

**What you now have:**
- ✅ Full-featured AI chat platform
- ✅ URL shortener with analytics
- ✅ Pastebin with syntax highlighting
- ✅ Video platform with transcoding
- ✅ Media import from various sources
- ✅ User management and authentication
- ✅ Discord integration
- ✅ Production-ready deployment

**Next steps:**
1. Invite users to your platform
2. Configure additional features
3. Set up monitoring and backups
4. Customize the platform for your needs

Welcome to the MeatLizard AI Platform! 🦎