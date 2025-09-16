# Administrator's Guide

This guide is for administrators of the MeatLizard AI Platform. It covers system management, user administration, and maintenance tasks.

## 1. Prerequisites

To be an administrator, your Discord account must have the "AI Admin" role. This role is configured in the `server/config.yml` file and must be created manually in your Discord server's settings.

## 2. Admin Slash Commands

All admin commands are prefixed with `/ai-admin`. They can only be used by users with the "AI Admin" role.

-   **/ai-admin status**:
    -   **Description**: Provides a real-time snapshot of the system's health.
    -   **Output**: An embed showing:
        -   `Client Bot Status`: ONLINE or OFFLINE.
        -   `Server Bot Uptime`: How long the server bot has been running.
        -   `Active Sessions`: The number of currently active chat sessions.
        -   `Inference Queue`: The number of requests waiting for the client-bot.
        -   `Tokens/Second (5m avg)`: The average token generation rate over the last 5 minutes.

-   **/ai-admin toggle `[service]`**:
    -   **Description**: Enables or disables key system features. Useful for maintenance or emergencies.
    -   **Arguments**:
        -   `service: requests`: Toggling this will prevent any new users from starting sessions or sending messages. Existing, in-progress requests will be completed.
        -   `service: fallback`: Toggling this will disable the server-side Markov chain generator. If the client-bot is offline, the system will simply show "unavailable" instead of generating a fallback response.

-   **/ai-admin transfer `[session_id]` `[new_user]`**:
    -   **Description**: Transfers ownership of an active session to a different Discord user. This is useful for support escalations.
    -   **Arguments**:
        -   `session_id`: The ID of the session to transfer (e.g., `sess_...`).
        -   `new_user`: The Discord user to transfer the session to.

-   **/ai-admin metrics `[timeframe]`**:
    -   **Description**: Generates a performance report and posts it to the current channel.
    -   **Arguments**:
        -   `timeframe`: `24h`, `7d`, or `30d`.
    -   **Output**: An embed with graphs (or text data) showing request volume, average tokens/sec, and client-bot uptime over the selected period.

-   **/ai-admin backup `[target]`**:
    -   **Description**: Manually triggers a backup job.
    -   **Arguments**:
        -   `target: database`: Creates a dump of the PostgreSQL database and uploads it to the S3 bucket.
        -   `target: transcripts`: Verifies that all completed sessions have their transcripts saved to S3 and re-uploads any that are missing.

-   **/ai-admin reboot `[target]`**:
    -   **Description**: Sends a command to gracefully restart a system component.
    -   **Arguments**:
        -   `target: client-bot`: The `server-bot` sends a special payload. The `client-bot` will finish its current job, send a confirmation, and then exit. The `launchd` service on the Mac will automatically restart it.
        -   `target: server-bot`: The bot will restart its own process. This should be used with caution.

## 3. User Management

### Banning a User

To ban a user, use the native Discord ban functionality. The `server-bot` will detect this and automatically prevent the banned user ID from starting new sessions.

### Making a User an Admin

Assign the "AI Admin" role to the user in your Discord server's settings.

## 4. Client-Bot Setup (macOS)

The `client-bot` is designed to be run on a dedicated Mac with Apple Silicon.

### 4.1. Initial Setup

1.  **Install Dependencies**:
    ```bash
    # Install Homebrew if you don't have it
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Install Python and other tools
    brew install python@3.11 cmake
    ```

2.  **Clone and Build `llama.cpp`**:
    ```bash
    git clone https://github.com/ggerganov/llama.cpp.git
    cd llama.cpp

    # Build with Metal (MPS) support
    make clean
    LLAMA_METAL=1 make
    ```
    This will create the `main` executable in the `llama.cpp` directory.

3.  **Download Models**:
    -   Download your desired GGUF-formatted models (e.g., from Hugging Face).
    -   Store them in a dedicated folder, e.g., `/Users/admin/ai/models/`.

4.  **Configure the Client Bot**:
    -   Copy the `client_bot/config.yml.example` to `client_bot/config.yml`.
    -   Edit the config file, filling in your bot token, server bot ID, and the correct paths to the `llama.cpp` executable and your models.

### 4.2. Running as a Service (`launchd`)

To ensure the `client-bot` runs continuously and restarts on reboot, you should run it as a `launchd` service.

1.  **Create a Launch Agent file**:
    -   Create a file at `~/Library/LaunchAgents/com.meat-lizard.client-bot.plist`.

2.  **Edit the `.plist` file**:
    ```xml
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>Label</key>
        <string>com.meat-lizard.client-bot</string>
        <key>ProgramArguments</key>
        <array>
            <string>/usr/local/bin/python3.11</string> <!-- Or path from 'which python3.11' -->
            <string>/Users/admin/MeatLizard-Infrastructure/client_bot/main.py</string> <!-- Absolute path to your bot's main script -->
        </array>
        <key>WorkingDirectory</key>
        <string>/Users/admin/MeatLizard-Infrastructure/client_bot</string> <!-- Absolute path to the bot's directory -->
        <key>RunAtLoad</key>
        <true/>
        <key>KeepAlive</key>
        <true/>
        <key>StandardOutPath</key>
        <string>/Users/admin/logs/client-bot.log</string>
        <key>StandardErrorPath</key>
        <string>/Users/admin/logs/client-bot.error.log</string>
    </dict>
    </plist>
    ```
    *   **Important**: Make sure to use the correct absolute paths for your Python executable, the bot script, and the working directory.

3.  **Load and start the service**:
    ```bash
    # Load the service
    launchctl load ~/Library/LaunchAgents/com.meat-lizard.client-bot.plist

    # Start it immediately
    launchctl start com.meat-lizard.client-bot
    ```

    The bot will now run in the background and restart automatically. You can check the log files for its output.
