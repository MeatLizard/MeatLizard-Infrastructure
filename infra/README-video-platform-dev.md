# Video Platform Development Environment

This directory contains the complete development environment setup for the MeatLizard Video Platform, including all necessary infrastructure components, monitoring, and deployment configurations.

## 🏗️ Architecture Overview

The development environment includes:

- **PostgreSQL 15**: Optimized database with video platform extensions
- **Redis Cluster**: Separate instances for caching and job queues
- **MinIO**: S3-compatible storage for video files and assets
- **FastAPI Web Server**: Main application with video platform APIs
- **Transcoding Workers**: FFmpeg-based video processing
- **Import Workers**: yt-dlp integration for media import
- **Nginx**: Reverse proxy and CDN simulation
- **Prometheus**: Metrics collection and monitoring
- **Grafana**: Monitoring dashboards and alerting

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- At least 8GB RAM and 50GB free disk space
- macOS, Linux, or Windows with WSL2

### Setup

1. **Clone and navigate to the project:**
   ```bash
   git clone <repository-url>
   cd MeatLizard-Infrastructure
   ```

2. **Run the setup script:**
   ```bash
   ./scripts/setup-video-platform-dev.sh
   ```

3. **Access the services:**
   - Web Interface: http://localhost:8000
   - Grafana Dashboard: http://localhost:3000 (admin/admin)
   - Prometheus: http://localhost:9090
   - MinIO Console: http://localhost:9001 (minioadmin/minioadmin123)

## 📋 Services Overview

### Core Services

| Service | Port | Description |
|---------|------|-------------|
| web | 8000 | FastAPI web server with video platform APIs |
| db | 5432 | PostgreSQL database with video optimizations |
| redis-master | 6379 | Redis for caching and sessions |
| redis-jobs | 6380 | Redis for background job queues |
| minio | 9000/9001 | S3-compatible storage with web console |

### Worker Services

| Service | Description |
|---------|-------------|
| transcoding-worker | FFmpeg-based video transcoding |
| import-worker | yt-dlp media import from external platforms |
| server-bot | Discord bot for platform integration |

### Monitoring Services

| Service | Port | Description |
|---------|------|-------------|
| nginx | 80/443 | Reverse proxy and CDN simulation |
| prometheus | 9090 | Metrics collection |
| grafana | 3000 | Monitoring dashboards |

## 🔧 Configuration

### Environment Variables

The main configuration is in `.env` file (created from `infra/.env.video-platform`):

```bash
# Database
DATABASE_DATABASE=meatlizard_video
DATABASE_USERNAME=postgres
DATABASE_PASSWORD=video_platform_dev_password_2024

# S3 Storage
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin123

# Video Processing
FFMPEG_PATH=/usr/bin/ffmpeg
MAX_VIDEO_SIZE_GB=10
TRANSCODING_CONCURRENCY=2

# Import Settings
YTDLP_PATH=/usr/local/bin/yt-dlp
IMPORT_CONCURRENCY=1
```

### Storage Buckets

The following S3 buckets are automatically created:

- `meatlizard-video-storage`: Original uploaded videos
- `meatlizard-video-transcoded`: Processed video files
- `meatlizard-video-thumbnails`: Video thumbnail images
- `meatlizard-video-hls`: HLS streaming segments

## 🎬 Video Platform Features

### Video Upload and Processing

1. **Upload Interface**: Web-based video upload with progress tracking
2. **Format Support**: MP4, MOV, AVI, MKV, WebM
3. **Quality Presets**: Automatic transcoding to multiple resolutions
4. **Thumbnail Generation**: Automatic thumbnail extraction
5. **HLS Streaming**: Adaptive bitrate streaming support

### Media Import (yt-dlp)

1. **Platform Support**: YouTube, TikTok, Instagram, Twitter, and more
2. **Quality Selection**: Configurable quality and format options
3. **Metadata Preservation**: Original title, description, and attribution
4. **Discord Integration**: Import via Discord bot commands

### Content Management

1. **Video Library**: Browse and search uploaded content
2. **Analytics**: View counts, engagement metrics, performance data
3. **Access Control**: Public, unlisted, and private video settings
4. **Content Moderation**: Administrative tools for content management

## 🛠️ Development Workflow

### Starting the Environment

```bash
# Start all services
docker compose -f infra/video-platform-dev.docker-compose.yml up -d

# View logs
docker compose -f infra/video-platform-dev.docker-compose.yml logs -f

# Stop services
docker compose -f infra/video-platform-dev.docker-compose.yml down
```

### Database Operations

```bash
# Run migrations
docker exec meatlizard-video-web alembic upgrade head

# Create new migration
docker exec meatlizard-video-web alembic revision --autogenerate -m "description"

# Access database
docker exec -it meatlizard-video-db psql -U postgres -d meatlizard_video
```

### Monitoring and Debugging

```bash
# Check service health
docker compose -f infra/video-platform-dev.docker-compose.yml ps

# View specific service logs
docker compose -f infra/video-platform-dev.docker-compose.yml logs -f web
docker compose -f infra/video-platform-dev.docker-compose.yml logs -f transcoding-worker

# Access service shell
docker exec -it meatlizard-video-web bash
docker exec -it meatlizard-transcoding-worker bash
```

### yt-dlp Management

```bash
# Update yt-dlp to latest version
./scripts/update-ytdlp.sh update

# Test platform support
./scripts/update-ytdlp.sh test

# Rebuild import worker
./scripts/update-ytdlp.sh rebuild

# Check status
./scripts/update-ytdlp.sh status
```

## 📊 Monitoring and Metrics

### Grafana Dashboards

Access Grafana at http://localhost:3000 (admin/admin) for:

- **System Overview**: CPU, memory, disk usage
- **Video Platform Metrics**: Upload rates, transcoding performance
- **Database Performance**: Query times, connection pools
- **Storage Metrics**: S3 usage, cache hit rates
- **Worker Performance**: Job queue status, processing times

### Prometheus Metrics

Key metrics collected:

- `video_uploads_total`: Total video uploads
- `transcoding_jobs_active`: Active transcoding jobs
- `transcoding_duration_seconds`: Transcoding processing time
- `import_jobs_total`: Media import job counts
- `storage_usage_bytes`: S3 storage utilization
- `database_connections_active`: Database connection pool status

### Health Checks

All services include health checks:

```bash
# Check overall system health
curl http://localhost:8000/health

# Check individual service health
docker compose -f infra/video-platform-dev.docker-compose.yml ps
```

## 🔒 Security Considerations

### Development Security

- All services run in isolated Docker network
- MinIO uses development credentials (change for production)
- Database uses development password (change for production)
- Nginx includes basic security headers
- Rate limiting configured for API endpoints

### Production Preparation

Before deploying to production:

1. Change all default passwords and keys
2. Configure proper SSL/TLS certificates
3. Set up proper backup procedures
4. Configure monitoring and alerting
5. Review and harden security settings

## 🐛 Troubleshooting

### Common Issues

1. **Services won't start**: Check Docker resources and port conflicts
2. **Database connection errors**: Ensure PostgreSQL is fully started
3. **Video upload fails**: Check disk space and file permissions
4. **Transcoding errors**: Verify FFmpeg installation and resources
5. **Import failures**: Check yt-dlp version and network connectivity

### Debug Commands

```bash
# Check Docker resources
docker system df
docker system prune

# Restart specific service
docker compose -f infra/video-platform-dev.docker-compose.yml restart web

# View detailed logs
docker compose -f infra/video-platform-dev.docker-compose.yml logs --tail=100 transcoding-worker

# Check network connectivity
docker exec meatlizard-video-web ping minio
docker exec meatlizard-video-web curl -I http://minio:9000
```

### Performance Tuning

For better performance on your development machine:

1. **Increase Docker resources**: 8GB+ RAM, 4+ CPU cores
2. **Use SSD storage**: Faster disk I/O for video processing
3. **Adjust worker concurrency**: Reduce if system is overloaded
4. **Enable GPU acceleration**: For faster transcoding (if available)

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp)
- [Docker Compose Reference](https://docs.docker.com/compose/)

## 🤝 Contributing

When contributing to the video platform:

1. Test changes in the development environment
2. Run the full test suite before submitting
3. Update documentation for new features
4. Follow the existing code style and patterns
5. Add appropriate monitoring and logging

## 📄 License

This project is part of the MeatLizard AI Platform. See the main project LICENSE file for details.