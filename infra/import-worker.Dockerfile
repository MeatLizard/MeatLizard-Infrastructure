# Import Worker Dockerfile with yt-dlp
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp with all optional dependencies
RUN pip install --no-cache-dir \
    yt-dlp[default] \
    mutagen \
    pycryptodome \
    websockets \
    brotli

# Set working directory
WORKDIR /app

# Copy requirements
COPY server/requirements.txt /app/server/requirements.txt
COPY requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

# Install import-specific dependencies
RUN pip install --no-cache-dir \
    celery \
    redis \
    prometheus-client \
    psutil \
    requests \
    aiohttp

# Copy application code
COPY server/ /app/server/
COPY shared_lib/ /app/shared_lib/

# Create necessary directories
RUN mkdir -p /app/temp /app/cache /app/logs

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV CELERY_BROKER_URL=redis://redis-jobs:6379/0
ENV CELERY_RESULT_BACKEND=redis://redis-jobs:6379/0

# Configure yt-dlp
ENV YTDLP_CACHE_DIR=/app/cache
ENV YTDLP_CONFIG_LOCATION=/app/cache/config

# Create yt-dlp configuration
RUN mkdir -p /app/cache && \
    echo "# yt-dlp configuration for video platform" > /app/cache/config && \
    echo "--no-check-certificate" >> /app/cache/config && \
    echo "--extract-flat" >> /app/cache/config && \
    echo "--write-info-json" >> /app/cache/config && \
    echo "--write-thumbnail" >> /app/cache/config && \
    echo "--embed-metadata" >> /app/cache/config

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import redis; r=redis.Redis(host='redis-jobs', port=6379, db=0); r.ping()" || exit 1

# Expose metrics port
EXPOSE 8002

# Default command
CMD ["python", "server/run_import_worker.py"]