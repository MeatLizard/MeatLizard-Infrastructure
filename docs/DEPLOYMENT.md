# Deployment Guide

This guide provides detailed instructions for deploying the MeatLizard AI Platform to a production environment.

## 1. Prerequisites

-   A server (VPS or dedicated) with Docker and Docker Compose installed for the server-side components.
-   A separate macOS machine with a powerful Apple Silicon GPU for the client-bot.
-   An S3-compatible object storage bucket and credentials.
-   Two Discord Bot applications created in the Discord Developer Portal (one for the Server-Bot, one for the Client-Bot).

## 2. Server-Side Deployment (Docker)

The server-side components (FastAPI, Server-Bot, PostgreSQL, Redis) are deployed using a single Docker Compose command.

### Step 1: Configuration

1.  Clone the repository to your server.
2.  Navigate to the `infra` directory.
3.  Copy the environment variable template: `cp env.copy .env`
4.  Edit the `.env` file and fill in all the required values:
    -   `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`: Your desired database credentials.
    -   `SERVER_BOT_TOKEN`: The token for your main Server-Bot.
    -   `CLIENT_BOT_ID`: The Application ID of your Client-Bot.
    -   `PAYLOAD_ENCRYPTION_KEY`: **CRITICAL.** Generate a new, secure 32-byte key using `openssl rand -hex 32`. This key must be identical on both the server and the client.
    -   `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `S3_REGION`: Your S3 bucket credentials and details.

### Step 2: Launch Services

Once the `.env` file is configured, launch the services:

```bash
docker compose up --build -d
```

This command will build the `web` and `server_bot` images, pull the official images for PostgreSQL and Redis, and start all services in detached mode.

### Step 3: Database Migration

After the containers are running, you must run the database migrations to set up the schema in the `meatdb` volume.

```bash
docker compose exec web alembic -c /app/server/alembic.ini upgrade head
```

The server is now live. You can check the status of the containers with `docker compose ps` and view logs with `docker compose logs web` or `docker compose logs server_bot`.

## 3. Client-Side Deployment (macOS)

The Client-Bot is designed to run directly on a macOS machine to take advantage of `llama.cpp` with Metal (MPS).

### Step 1: Setup llama.cpp

1.  Clone and build `llama.cpp` on the macOS machine. Follow the official instructions, ensuring you build with Metal support (`make LLAMA_METAL=1`).
2.  Download your desired GGUF-formatted LLM models (e.g., from Hugging Face) and place them in a known location.

### Step 2: Configure the Client-Bot

1.  Clone the repository to the macOS machine.
2.  Navigate to the `client/client_bot` directory.
3.  Create a `.env` file and add the following values:
    -   `CLIENT_BOT_TOKEN`: The token for your Client-Bot.
    -   `PAYLOAD_ENCRYPTION_KEY`: The **exact same** key you generated for the server's `.env` file.
    -   `DISCORD_GUILD_ID`: The ID of the Discord server where the bots will operate.
    -   `METRICS_CHANNEL_ID`: The ID of the channel where the bot should post metrics.
    -   Update the model paths in `client/client_bot/bot.py` to point to your downloaded `.gguf` files.

### Step 3: Install Dependencies and Run

1.  Create a virtual environment and install the required Python packages:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
2.  Run the bot:
    ```bash
    python run.py
    ```

For a more robust deployment, consider running the bot as a `launchd` service to ensure it restarts automatically.