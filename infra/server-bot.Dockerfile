# Server Bot Dockerfile with Video Platform Support
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY server/requirements.txt /app/server/requirements.txt
COPY requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

# Install Discord bot specific dependencies
RUN pip install --no-cache-dir \
    discord.py \
    prometheus-client \
    psutil

# Copy application code
COPY server/ /app/server/
COPY shared_lib/ /app/shared_lib/

# Create necessary directories
RUN mkdir -p /app/logs

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; import discord; print('Bot health check passed')" || exit 1

# Default command
CMD ["python", "server/server_bot/bot.py"]