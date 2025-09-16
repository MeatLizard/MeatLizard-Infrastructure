# Deployment Guide

This guide provides instructions for deploying the MeatLizard AI Platform to a production environment.

## 1. Deployment Overview

The deployment is a two-part process:

1.  **Server-Side Deployment**: The FastAPI app, `server-bot`, PostgreSQL, and Redis are deployed as Docker containers on a Linux server.
2.  **Client-Side Deployment**: The `client-bot` is deployed on a dedicated macOS machine with Apple Silicon, managed by `launchd`.

## 2. Server Deployment (Linux Server)

### 2.1. Prerequisites

-   A Linux server (e.g., Ubuntu 22.04) with Docker and `docker-compose` installed.
-   An S3-compatible object storage bucket and credentials.
-   A registered domain name.
-   `nginx` or another reverse proxy for handling HTTPS.

### 2.2. Setup Steps

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/your-username/MeatLizard-Infrastructure.git
    cd MeatLizard-Infrastructure
    ```

2.  **Configure Environment Variables**:
    -   Create a `.env` file from the `.env.example`.
    -   **CRITICAL**: Fill in all the required production values:
        -   `POSTGRES_PASSWORD`: A strong, randomly generated password.
        -   `SERVER_BOT_TOKEN`, `CLIENT_BOT_TOKEN`: Your Discord bot tokens.
        -   `PAYLOAD_ENCRYPTION_KEY`: A secure, randomly generated 32-byte hex key.
        -   `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`: Your S3 credentials.
    -   Ensure `ENVIRONMENT` is set to `production`.

3.  **Use the Production Docker Compose File**:
    -   The project includes a `docker-compose.prod.yml` (or similar) which is optimized for production. It may use different port mappings or volume strategies.
    ```bash
    docker-compose -f docker-compose.prod.yml up --build -d
    ```
    This will build and start all the server-side containers in detached mode.

4.  **Set Up a Reverse Proxy (Nginx)**:
    -   You must terminate HTTPS at a reverse proxy. Do not expose the FastAPI `uvicorn` server directly to the internet.
    -   Install `nginx` and `certbot` (for Let's Encrypt SSL certificates).
    -   Example `nginx` configuration:
        ```nginx
        server {
            listen 80;
            server_name your.domain.com;

            # Redirect HTTP to HTTPS
            location / {
                return 301 https://$host$request_uri;
            }
        }

        server {
            listen 443 ssl;
            server_name your.domain.com;

            ssl_certificate /etc/letsencrypt/live/your.domain.com/fullchain.pem;
            ssl_certificate_key /etc/letsencrypt/live/your.domain.com/privkey.pem;
            include /etc/letsencrypt/options-ssl-nginx.conf;
            ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

            location / {
                proxy_pass http://127.0.0.1:8000; # Proxy to the FastAPI container
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            }
        }
        ```

5.  **Apply Database Migrations**:
    ```bash
    docker-compose -f docker-compose.prod.yml exec web alembic upgrade head
    ```

## 3. Client Deployment (macOS Machine)

The `client-bot` runs directly on macOS to take advantage of Metal GPU acceleration.

### 3.1. Prerequisites

-   A Mac with an M1, M2, or M3 series chip.
-   macOS Monterey or newer.
-   A stable internet connection.
-   The user account for the bot should be configured to log in automatically on reboot.

### 3.2. Setup Steps

1.  **Install Dependencies**:
    -   Follow the instructions in the [Admin Guide](./ADMIN_GUIDE.md#41-initial-setup) to install Homebrew, Python, and build `llama.cpp`.

2.  **Clone the Repository**:
    ```bash
    git clone https://github.com/your-username/MeatLizard-Infrastructure.git
    cd MeatLizard-Infrastructure/client_bot
    ```

3.  **Install Python Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure the Bot**:
    -   Create a `config.yml` file.
    -   Fill in the `client_bot.token` and `payload_encryption_key`. The encryption key **must** match the one on the server.
    -   Verify all paths to your `llama.cpp` executable and models are correct.

5.  **Run as a `launchd` Service**:
    -   Follow the instructions in the [Admin Guide](./ADMIN_GUIDE.md#42-running-as-a-service-launchd) to create and load the `.plist` file. This is the recommended way to run the bot in production.

## 4. Backups and Restore

### 4.1. Database Backups

-   **Strategy**: A cron job on the host machine or a separate Docker container should periodically run `pg_dump` and upload the result to S3.
-   **Example Backup Script**:
    ```bash
    #!/bin/bash
    DB_CONTAINER="meat-lizard-db"
    DB_NAME="meatdb"
    DB_USER="user"
    S3_BUCKET="s3://meat-lizard-backups/db"
    DATE=$(date +"%Y-%m-%d_%H-%M-%S")

    docker exec $DB_CONTAINER pg_dump -U $DB_USER -d $DB_NAME | gzip > /tmp/backup-$DATE.sql.gz
    aws s3 cp /tmp/backup-$DATE.sql.gz $S3_BUCKET/
    rm /tmp/backup-$DATE.sql.gz
    ```

### 4.2. Restore Procedure

1.  Stop the FastAPI and `server-bot` containers.
2.  Download the desired backup file from S3.
3.  Execute a command like the following:
    ```bash
    gunzip < backup.sql.gz | docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME
    ```
4.  Restart the application containers.
