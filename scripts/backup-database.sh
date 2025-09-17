#!/bin/bash

# MeatLizard AI Platform Database Backup Script
# Creates comprehensive backups of the database and important files

set -e

# Configuration
BACKUP_DIR="backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="meatlizard_backup_$DATE"
RETENTION_DAYS=30

echo "🦎 MeatLizard Database Backup"
echo "============================="
echo "Backup name: $BACKUP_NAME"
echo "Date: $(date)"
echo ""

# Create backup directory
mkdir -p $BACKUP_DIR

# Check if Docker is running
if ! docker-compose ps >/dev/null 2>&1; then
    echo "❌ Docker Compose services not running"
    exit 1
fi

# Database backup
echo "🗄️  Creating database backup..."
docker-compose exec -T postgres pg_dump -U meatlizard -h localhost meatlizard > "$BACKUP_DIR/${BACKUP_NAME}_database.sql"
echo "✅ Database backup created: ${BACKUP_NAME}_database.sql"

# Configuration backup
echo "📁 Backing up configuration files..."
tar -czf "$BACKUP_DIR/${BACKUP_NAME}_config.tar.gz" \
    .env \
    docker-compose.yml \
    client_bot/config.yml \
    infra/ \
    scripts/ \
    2>/dev/null || echo "⚠️  Some config files may not exist"
echo "✅ Configuration backup created: ${BACKUP_NAME}_config.tar.gz"

# Media files backup (if not too large)
if [ -d "media" ]; then
    MEDIA_SIZE=$(du -sm media | cut -f1)
    if [ $MEDIA_SIZE -lt 1000 ]; then  # Less than 1GB
        echo "📸 Backing up media files..."
        tar -czf "$BACKUP_DIR/${BACKUP_NAME}_media.tar.gz" media/
        echo "✅ Media backup created: ${BACKUP_NAME}_media.tar.gz"
    else
        echo "⚠️  Media directory too large ($MEDIA_SIZE MB), skipping media backup"
        echo "   Consider using S3 sync for media files"
    fi
fi

# Logs backup
if [ -d "logs" ]; then
    echo "📋 Backing up logs..."
    tar -czf "$BACKUP_DIR/${BACKUP_NAME}_logs.tar.gz" logs/
    echo "✅ Logs backup created: ${BACKUP_NAME}_logs.tar.gz"
fi

# Create comprehensive backup archive
echo "📦 Creating comprehensive backup archive..."
cd $BACKUP_DIR
tar -czf "${BACKUP_NAME}_complete.tar.gz" ${BACKUP_NAME}_*
cd ..

# Calculate backup size
BACKUP_SIZE=$(du -sh "$BACKUP_DIR/${BACKUP_NAME}_complete.tar.gz" | cut -f1)
echo "✅ Complete backup created: ${BACKUP_NAME}_complete.tar.gz ($BACKUP_SIZE)"

# Clean up individual files (keep only the complete archive)
rm -f "$BACKUP_DIR/${BACKUP_NAME}_database.sql"
rm -f "$BACKUP_DIR/${BACKUP_NAME}_config.tar.gz"
rm -f "$BACKUP_DIR/${BACKUP_NAME}_media.tar.gz" 2>/dev/null || true
rm -f "$BACKUP_DIR/${BACKUP_NAME}_logs.tar.gz" 2>/dev/null || true

# Clean up old backups
echo "🧹 Cleaning up old backups (older than $RETENTION_DAYS days)..."
find $BACKUP_DIR -name "meatlizard_backup_*" -type f -mtime +$RETENTION_DAYS -delete
REMAINING_BACKUPS=$(ls -1 $BACKUP_DIR/meatlizard_backup_* 2>/dev/null | wc -l)
echo "✅ Cleanup complete. $REMAINING_BACKUPS backups remaining."

# Display backup information
echo ""
echo "📊 Backup Summary"
echo "================="
echo "Backup file: $BACKUP_DIR/${BACKUP_NAME}_complete.tar.gz"
echo "Backup size: $BACKUP_SIZE"
echo "Backup date: $(date)"
echo "Retention: $RETENTION_DAYS days"
echo ""

# Optional: Upload to S3 if configured
if [ ! -z "$S3_BUCKET_NAME" ] && [ ! -z "$S3_ACCESS_KEY_ID" ]; then
    echo "☁️  Uploading backup to S3..."
    if command -v aws &> /dev/null; then
        aws s3 cp "$BACKUP_DIR/${BACKUP_NAME}_complete.tar.gz" "s3://$S3_BUCKET_NAME/backups/"
        echo "✅ Backup uploaded to S3: s3://$S3_BUCKET_NAME/backups/${BACKUP_NAME}_complete.tar.gz"
    else
        echo "⚠️  AWS CLI not installed, skipping S3 upload"
    fi
fi

echo ""
echo "🎉 Backup completed successfully!"
echo ""
echo "To restore from this backup:"
echo "1. Extract: tar -xzf $BACKUP_DIR/${BACKUP_NAME}_complete.tar.gz"
echo "2. Restore database: docker-compose exec -T postgres psql -U meatlizard -d meatlizard < ${BACKUP_NAME}_database.sql"
echo "3. Restore config files from the extracted archive"
echo ""