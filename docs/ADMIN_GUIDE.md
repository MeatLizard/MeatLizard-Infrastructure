# Administrator's Guide

This guide is for administrators of a deployed MeatLizard AI Platform. It covers system management, user administration, and routine maintenance tasks. For initial setup and deployment, please see the [Deployment Guide](./DEPLOYMENT.md).

## 1. Admin Role Requirement

To be an administrator, your Discord account must have the role specified in the `admin_role_id` of your server's configuration. Without this role, you will not be able to use any of the commands listed below.

## 2. Admin Slash Commands

All admin commands are prefixed with `/ai-admin`. They can only be used by users with the admin role.

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
        -   `target: server-bot`: The bot will restart its own process. This should be used with caution as it may cause a few seconds of downtime.

## 3. User Management

### Banning a User

To ban a user from the AI service, use the native Discord ban functionality in your server settings (`Server Settings > Bans > Add Ban`). The `server-bot` will check against Discord's ban list and prevent banned user IDs from starting new sessions.

### Making a User an Admin

Assign the designated "AI Admin" role to the user in your Discord server's settings (`Server Settings > Roles`).

## 4. Routine Maintenance

### Checking Server Logs

You can check the logs of the running server components using `docker compose`.
```bash
# SSH into your Debian server and navigate to the infra directory
cd MeatLizard-Infrastructure/infra

# View logs for all services
docker compose logs -f

# View logs for a specific service (e.g., the web server)
docker compose logs -f web
```

### Checking Client Logs

The client bot's logs are stored in the files defined in its `launchd` service file.
```bash
# SSH into your Mac or open Terminal.app
# View the standard output log
tail -f ~/logs/client-bot.log

# View the error log in a new terminal
tail -f ~/logs/client-bot.error.log
```

### Updating the Application

1.  **Server**:
    ```bash
    # SSH into your Debian server
    cd MeatLizard-Infrastructure
    git pull
    cd infra
    docker compose up --build -d # This will rebuild and restart the containers
    docker compose exec web alembic upgrade head # Apply any new database migrations
    ```

2.  **Client**:
    ```bash
    # SSH into your Mac
    cd ~/dev/MeatLizard-Infrastructure
    git pull
    cd client_bot
    source venv/bin/activate
    pip install -r requirements.txt # Update dependencies
    # Restart the service to apply changes
    launchctl stop com.meatlizard.clientbot
    launchctl start com.meatlizard.clientbot
    ```