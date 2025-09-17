# Transcoding Worker Dockerfile
FROM python:3.11-slim

# Install FFmpeg and system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    wget \
    git \
    build-essential \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libavfilter-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY server/requirements.txt /app/server/requirements.txt
COPY requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

# Install transcoding-specific dependencies
RUN pip install --no-cache-dir \
    celery \
    redis \
    prometheus-client \
    psutil \
    pillow \
    opencv-python-headless \
    ffmpeg-python

# Copy application code
COPY server/ /app/server/
COPY shared_lib/ /app/shared_lib/

# Create necessary directories
RUN mkdir -p /app/temp /app/logs /dev/shm

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV CELERY_BROKER_URL=redis://redis-jobs:6379/0
ENV CELERY_RESULT_BACKEND=redis://redis-jobs:6379/0

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import redis; r=redis.Redis(host='redis-jobs', port=6379, db=0); r.ping()" || exit 1

# Expose metrics port
EXPOSE 8001

# Default command
CMD ["python", "server/run_transcoding_worker.py"]