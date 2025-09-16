# Configuration Examples (YAML)

This document provides example YAML configuration files for the different components of the MeatLizard AI Platform. In a production deployment, these values should be managed securely, for example via environment variables or a secrets management system.

---

## 1. Server Configuration (`server/config.yml`)

This file would be used by the FastAPI application and the `server-bot`.

```yaml
# --- General Settings ---
environment: "production" # "development" or "production"
log_level: "INFO"

# --- Database & Cache ---
database:
  dsn: "postgresql://user:password@postgres:5432/meatdb"
redis:
  host: "redis"
  port: 6379

# --- Discord Bot Settings (Server-Side) ---
server_bot:
  token: "your_server_bot_discord_token_here"
  client_bot_id: "the_discord_user_id_of_your_client_bot"
  admin_role_id: "the_discord_role_id_for_admins"
  metrics_channel_id: "the_channel_id_for_posting_metrics"
  transcript_channel_id: "the_channel_id_for_posting_transcripts"

# --- Security ---
# The 32-byte (64 hex characters) key for AES-256-GCM encryption
# Generate with: openssl rand -hex 32
payload_encryption_key: "your_super_secret_64_character_hex_key_here"
allowed_origins: # For FastAPI CORS
  - "http://localhost:3000"
  - "https://your.website.com"

# --- Storage ---
storage:
  provider: "s3" # or "local"
  s3:
    aws_access_key_id: "your_s3_access_key"
    aws_secret_access_key: "your_s3_secret_key"
    bucket_name: "meat-lizard-transcripts"
    region: "us-east-1"
    endpoint_url: null # Optional: for MinIO or other S3-compatibles

# --- Fallback Mode ---
fallback_generator:
  enabled: true
  type: "markov" # or "echo"
  markov_state_size: 2

```

---

## 2. Client Configuration (`client_bot/config.yml`)

This file would be used by the `client-bot` running on the macOS machine.

```yaml
# --- Discord Bot Settings (Client-Side) ---
client_bot:
  token: "your_client_bot_discord_token_here"
  server_bot_id: "the_discord_user_id_of_your_server_bot"

# --- Security ---
# This MUST be the same key used in the server configuration.
payload_encryption_key: "your_super_secret_64_character_hex_key_here"

# --- llama.cpp Settings ---
llama_cpp:
  # Path to the compiled llama.cpp 'main' executable
  executable_path: "/Users/admin/ai/llama.cpp/main"
  # Default context size
  n_ctx: 4096
  # Number of CPU threads to use
  threads: 8
  # Number of layers to offload to the GPU.
  # This is highly dependent on the model and your Mac's RAM.
  # A value of 35 is often good for 7B models on M1/M2 with 16GB+ RAM.
  # Set to 0 to disable GPU acceleration.
  n_gpu_layers: 35

# --- Model Mapping ---
# This section maps the friendly 'model_alias' from the server's request
# to the actual GGUF model file on the local filesystem.
models:
  - alias: "vicuna-13b-v1.5"
    path: "/Users/admin/ai/models/vicuna-13b-v1.5.Q5_K_M.gguf"
  - alias: "llama2-70b-chat"
    path: "/Users/admin/ai/models/llama-2-70b-chat.Q4_K_M.gguf"
  - alias: "default" # A fallback if the requested alias is not found
    path: "/Users/admin/ai/models/vicuna-13b-v1.5.Q5_K_M.gguf"

# --- Health & Monitoring ---
monitoring:
  # Enable graceful shutdown on low battery
  enable_battery_monitor: true
  # Shutdown if battery percentage is below this value
  low_battery_threshold_percent: 20
  # Post GPU/CPU metrics to the server
  enable_system_metrics: true
  # How often to post metrics (in seconds)
  metrics_post_interval: 300

```
