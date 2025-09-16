# Production Deployment Guide

This is a comprehensive, step-by-step guide to deploying the MeatLizard AI Platform to a production environment. This guide assumes you are starting from bare-bones systems.

**Deployment consists of two primary parts:**
1.  **The Server**: A Debian 12 VPS running the web application, server-bot, and databases.
2.  **The Client**: An Apple Silicon Mac running the LLM inference client-bot.

---

## Part 1: Server Deployment (Debian 12 VPS)

This section covers the setup of a fresh Debian 12 server to host the main application stack.

### 1.1: Initial Server Preparation

1.  **Connect to your VPS**:
    Connect to your server as the `root` user via SSH.
    ```bash
    ssh root@YOUR_SERVER_IP
    ```

2.  **Create a Sudo User**:
    Running everything as `root` is insecure. Create a new user and give it `sudo` privileges.
    ```bash
    # Create the user (replace 'meatadmin' with your desired username)
    adduser meatadmin

    # Add the user to the 'sudo' group
    usermod -aG sudo meatadmin

    # Log out of the root account and log back in as the new user
    exit
    ssh meatadmin@YOUR_SERVER_IP
    ```

3.  **Basic Firewall Setup (UFW)**:
    Enable the Uncomplicated Firewall (UFW) to block all ports except those we need.
    ```bash
    # Allow SSH, HTTP, and HTTPS traffic
    sudo ufw allow OpenSSH
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp

    # Enable the firewall
    sudo ufw enable
    ```

4.  **Update System Packages**:
    Ensure your system is up-to-date.
    ```bash
    sudo apt update && sudo apt upgrade -y
    ```

### 1.2: Install Core Dependencies

1.  **Install Git, Nginx, and Certbot**:
    ```bash
    sudo apt install -y git nginx python3-certbot-nginx
    ```

2.  **Install Docker and Docker Compose**:
    We will use Docker's official repository for the latest version.
    ```bash
    # Add Docker's official GPG key:
    sudo apt-get install -y ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    # Add the repository to Apt sources:
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update

    # Install Docker Engine, CLI, and Compose
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Add your user to the 'docker' group to run docker commands without 'sudo'
    sudo usermod -aG docker ${USER}

    # You will need to log out and log back in for this change to take effect.
    echo "Log out and log back in, then proceed to the next step."
    exit
    ```
    **Action Required**: Log out and SSH back into your server.

### 1.3: Application Setup

1.  **Clone the Repository**:
    ```bash
    # ssh meatadmin@YOUR_SERVER_IP
    git clone https://github.com/your-username/MeatLizard-Infrastructure.git
    cd MeatLizard-Infrastructure
    ```

2.  **Create Discord Bot Applications**:
    You need two separate "applications" from the Discord Developer Portal.
    -   Go to: [https://discord.com/developers/applications](https://discord.com/developers/applications)
    -   **Create Application #1 (Server Bot)**:
        -   Click "New Application", give it a name (e.g., "MeatLizard Server").
        -   Go to the "Bot" tab.
        -   Enable `MESSAGE CONTENT INTENT` under "Privileged Gateway Intents".
        -   Click "Reset Token" to get your **Server Bot Token**. Save this.
        -   Copy the **Application ID**. This is your Server Bot's ID.
    -   **Create Application #2 (Client Bot)**:
        -   Click "New Application", give it a name (e.g., "MeatLizard Client").
        -   Go to the "Bot" tab.
        -   You do *not* need privileged intents for this bot.
        -   Click "Reset Token" to get your **Client Bot Token**. Save this.
        -   Copy the **Application ID**. This is your Client Bot's ID.

3.  **Configure Environment Variables**:
    This is the most critical configuration step.
    ```bash
    # Navigate to the infra directory
    cd infra

    # Create the .env file
    cp ../.env.example .env
    nano .env
    ```
    Fill in the `.env` file with your secrets. **Do not leave defaults.**
    ```ini
    # ---
    CORE
    ---
    ENVIRONMENT=production

    # ---
    DATABASE
    ---
    # Use a strong, random password. Generate with: openssl rand -hex 16
    POSTGRES_PASSWORD=YOUR_STRONG_DB_PASSWORD
    POSTGRES_USER=meatuser
    POSTGRES_DB=meatdb

    # ---
    DISCORD BOTS
    ---
    # From Step 1.3.2
    SERVER_BOT_TOKEN=your_server_bot_discord_token_here
    CLIENT_BOT_ID=the_client_bots_application_id_here

    # ---
    SECURITY
    ---
    # CRITICAL: Generate a secure random key.
    # Run this command on your local machine or the server: openssl rand -hex 32
    PAYLOAD_ENCRYPTION_KEY=your_generated_64_character_hex_key_here

    # ---
    S3 STORAGE
    ---
    # Your S3 bucket details
    S3_ACCESS_KEY_ID=your_s3_access_key
    S3_SECRET_ACCESS_KEY=your_s3_secret_key
    S3_BUCKET_NAME=meat-lizard-transcripts
    S3_REGION=us-east-1
    ```

### 1.4: Nginx and SSL Configuration

1.  **Configure Nginx**:
    Create a new Nginx configuration file for your site.
    ```bash
    sudo nano /etc/nginx/sites-available/meatlizard
    ```
    Paste the following configuration, replacing `your.domain.com` with your actual domain.
    ```nginx
    server {
        listen 80;
        server_name your.domain.com;

        location / {
            proxy_pass http://127.0.0.1:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
    ```

2.  **Enable the Site**:
    ```bash
    sudo ln -s /etc/nginx/sites-available/meatlizard /etc/nginx/sites-enabled/
    sudo nginx -t # Test the configuration
    sudo systemctl reload nginx
    ```

3.  **Obtain SSL Certificate with Certbot**:
    Certbot will automatically edit your Nginx config to enable HTTPS.
    ```bash
    sudo certbot --nginx -d your.domain.com
    ```
    Follow the on-screen prompts. It will ask if you want to redirect HTTP to HTTPS; choose to redirect.

### 1.5: Launch the Application

1.  **Start Docker Containers**:
    From the `MeatLizard-Infrastructure/infra` directory (where your `docker-compose.yml` is):
    ```bash
    docker compose up --build -d
    ```
    This command builds the images, starts the containers in detached mode, and will restart them on reboot.

2.  **Run Database Migrations**:
    The database needs its schema. Run the Alembic migration command inside the `web` container.
    ```bash
    docker compose exec web alembic upgrade head
    ```

3.  **Check Logs**:
    Verify that everything started correctly.
    ```bash
    docker compose logs -f
    ```
    You should see logs from the `web` and `server_bot` containers. Press `Ctrl+C` to exit. Your application is now live.

---

## Part 2: Client Deployment (Apple Silicon Mac)

This section covers the setup of a dedicated Mac to run the `client-bot` for LLM inference.

### 2.1: Initial Mac Preparation

1.  **Install Homebrew**:
    If you don't have it, open `Terminal.app` and run:
    ```bash
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    ```
    Follow the on-screen instructions to add Homebrew to your PATH.

2.  **Install Dependencies**:
    ```bash
    brew install git python@3.11 cmake
    ```

3.  **System Settings for 24/7 Operation**:
    -   **Energy Saver**: Go to `System Settings > Energy Saver`. Set "Turn display off after" to "Never". Ensure "Prevent your Mac from sleeping automatically when the display is off" is checked.
    -   **Login**: Go to `System Settings > Users & Groups > Login Options`. Enable "Automatic login" for the user account that will run the bot. This ensures the bot can restart after a power outage and reboot.

### 2.2: Build `llama.cpp`

1.  **Clone the Repository**:
    Choose a location for your AI tools, e.g., `~/dev/ai`.
    ```bash
    mkdir -p ~/dev/ai
    cd ~/dev/ai
    git clone https://github.com/ggerganov/llama.cpp.git
    ```

2.  **Build with Metal (MPS) Support**:
    This is the key step for GPU acceleration.
    ```bash
    cd llama.cpp
    make clean
    LLAMA_METAL=1 make
    ```
    This creates the `main` executable inside the `llama.cpp` directory. Note its absolute path: `~/dev/ai/llama.cpp/main`.

3.  **Download Models**:
    Download your desired GGUF-formatted models and store them in a dedicated folder, e.g., `~/dev/ai/models`.

### 2.3: Application Setup

1.  **Clone Your Repository**:
    ```bash
    cd ~/dev
    git clone https://github.com/your-username/MeatLizard-Infrastructure.git
    cd MeatLizard-Infrastructure/client_bot
    ```

2.  **Set up Python Virtual Environment**:
    ```bash
    python3.11 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Configure the Client Bot**:
    Create and edit the configuration file.
    ```bash
    cp config.yml.example config.yml
    nano config.yml
    ```
    Fill in the details. **Paths must be absolute.**
    ```yaml
    client_bot:
      token: "your_client_bot_discord_token_here" # From Step 1.3.2
      server_bot_id: "the_server_bots_application_id_here"

    payload_encryption_key: "your_generated_64_character_hex_key_here" # MUST MATCH THE SERVER .env FILE

    llama_cpp:
      executable_path: "/Users/your_username/dev/ai/llama.cpp/main" # Absolute path
      n_ctx: 4096
      threads: 8
      n_gpu_layers: 35 # Adjust based on your model and Mac's RAM

    models:
      - alias: "default"
        path: "/Users/your_username/dev/ai/models/your-default-model.Q5_K_M.gguf" # Absolute path
      - alias: "vicuna-13b-v1.5"
        path: "/Users/your_username/dev/ai/models/vicuna-13b-v1.5.Q5_K_M.gguf" # Absolute path
    ```

### 2.4: Run as a Persistent Service (`launchd`)

This ensures the bot runs on startup and restarts if it crashes.

1.  **Create a Log Directory**:
    ```bash
    mkdir -p ~/logs
    ```

2.  **Create the `launchd` .plist file**:
    ```bash
    nano ~/Library/LaunchAgents/com.meatlizard.clientbot.plist
    ```
    Paste the following, **carefully replacing all paths** with your user's absolute paths.
    ```xml
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>Label</key>
        <string>com.meatlizard.clientbot</string>
        <key>ProgramArguments</key>
        <array>
            <!-- Absolute path to python executable inside your venv -->
            <string>/Users/your_username/dev/MeatLizard-Infrastructure/client_bot/venv/bin/python</string>
            <!-- Absolute path to the bot's main script -->
            <string>/Users/your_username/dev/MeatLizard-Infrastructure/client_bot/main.py</string>
        </array>
        <key>WorkingDirectory</key>
        <!-- Absolute path to the bot's directory -->
        <string>/Users/your_username/dev/MeatLizard-Infrastructure/client_bot</string>
        <key>RunAtLoad</key>
        <true/>
        <key>KeepAlive</key>
        <true/>
        <key>StandardOutPath</key>
        <string>/Users/your_username/logs/client-bot.log</string>
        <key>StandardErrorPath</key>
        <string>/Users/your_username/logs/client-bot.error.log</string>
    </dict>
    </plist>
    ```

3.  **Load and Start the Service**:
    ```bash
    # Unload any previous versions first
    launchctl unload ~/Library/LaunchAgents/com.meatlizard.clientbot.plist

    # Load the new service definition
    launchctl load ~/Library/LaunchAgents/com.meatlizard.clientbot.plist

    # Start it now
    launchctl start com.meatlizard.clientbot
    ```

4.  **Verify it's Running**:
    Check the log files to see the bot's output.
    ```bash
    tail -f ~/logs/client-bot.log
    ```
    The client is now deployed and will run persistently.