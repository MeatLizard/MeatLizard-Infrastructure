# Video Platform Web Server Dockerfile
FROM python:3.11-slim

# Install system dependencies for video processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    wget \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp
RUN pip install --no-cache-dir yt-dlp

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY server/requirements.txt /app/server/requirements.txt
COPY requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

# Install additional video platform dependencies
RUN pip install --no-cache-dir \
    prometheus-client \
    psutil \
    pillow \
    opencv-python-headless \
    moviepy

# Copy application code
COPY server/ /app/server/
COPY shared_lib/ /app/shared_lib/

# Create necessary directories
RUN mkdir -p /app/uploads /app/temp /app/logs

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Default command
CMD ["uvicorn", "server.web.app.main:app", "--host", "0.0.0.0", "--port", "8000"]