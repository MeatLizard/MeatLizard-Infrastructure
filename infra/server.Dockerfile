# infra/server.Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables to prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Add Python's user binary directory to the PATH
ENV PATH="/root/.local/bin:${PATH}"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Add any system dependencies here if needed (e.g., for psycopg2)
    # build-essential libpq-dev
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY ./server/requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY ./server /app/server
COPY ./shared_lib /app/shared_lib

# Expose the port the app runs on
EXPOSE 8000

# Define a command to run the application.
# This can be overridden in docker-compose.
# We'll use a startup script to run migrations and then the app.
# For now, this is a placeholder.
CMD ["uvicorn", "server.web.app.main:app", "--host", "0.0.0.0", "--port", "8000"]