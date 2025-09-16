# MeatLizard AI Chat Platform

MeatLizard is a production-ready, two-part AI chat system featuring a FastAPI web UI and a powerful Discord bot ecosystem for managing AI inference and user interactions.

![Architecture Diagram](docs/architecture.png) <!--- Placeholder for diagram -->

This platform is designed for performance, security, and scalability, leveraging a dedicated client-side bot for GPU-accelerated LLM inference on Apple Silicon hardware.

## Table of Contents

-   [Features](#features)
-   [Architecture](#architecture)
-   [Getting Started](#getting-started)
-   [Documentation](#documentation)
-   [Security](#security)
-   [Contributing](#contributing)

## Features

-   **Hybrid Chat Interface**: Seamlessly interact with the AI via a web UI or Discord.
-   **High-Performance Inference**: Utilizes `llama.cpp` with Apple Metal (MPS) for fast, local inference on macOS hardware.
-   **Secure & Private Sessions**: Each chat session occurs in a private, permissions-controlled Discord channel.
-   **End-to-End Encrypted Messaging**: Payloads between server and client bots are secured with AES-256-GCM.
-   **Graceful Offline Fallback**: Switches to a lightweight Markov chain generator if the primary client-bot is unavailable.
-   **Comprehensive Admin Dashboard**: Full control over the system via Discord slash commands.
-   **Detailed Metrics & Monitoring**: Real-time metrics on token throughput, GPU usage, and uptime posted to a dedicated channel.
-   **Automated Transcripts & Backups**: Securely archives chat transcripts to S3 and performs regular database backups.
-   **Scalable Architecture**: Built with FastAPI, Celery, PostgreSQL, and Redis to handle production workloads.

## Architecture

The system is composed of two main parts:

1.  **The Server**: A FastAPI application that provides the web interface and a `server-bot` that orchestrates sessions, permissions, and data management within Discord.
2.  **The Client**: A `client-bot` that runs on dedicated macOS hardware, handling all LLM inference requests.

For a detailed breakdown, see the [Architecture Documentation](docs/ARCHITECTURE.md).

## Getting Started

To get the development environment running, you will need Docker, Colima (or Docker Desktop), and Python 3.11+.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/MeatLizard-Infrastructure.git
    cd MeatLizard-Infrastructure
    ```

2.  **Set up the server:**
    -   See the [Deployment Guide](docs/DEPLOYMENT.md) for full instructions.

3.  **Set up the client:**
    -   See the [Client Setup Guide](docs/ADMIN_GUIDE.md#client-bot-setup) for instructions on configuring the `llama.cpp` client.

## Documentation

This project is documented in the `/docs` directory.

-   **[README.md](docs/README.md)**: (This file) High-level overview.
-   **[Architecture.md](docs/ARCHITECTURE.md)**: Detailed system architecture, data flow diagrams, and component descriptions.
-   **[Admin Guide](docs/ADMIN_GUIDE.md)**: Instructions for administrators on managing the system, using slash commands, and performing maintenance.
-   **[Deployment Guide](docs/DEPLOYMENT.md)**: Step-by-step instructions for deploying the server and client.
-   **[Developer Guide](docs/DEVELOPER_GUIDE.md)**: Information for developers, including code style, testing procedures, and contribution guidelines.
-   **[Security.md](docs/SECURITY.md)**: A guide to the security features of the platform and best practices.
-   **[Prompt Library](docs/PROMPT_LIBRARY.md)**: A collection of curated system and user prompts.

## Security

Security is a core design principle of this platform. All sensitive operations require administrative privileges, communication is encrypted, and data is stored securely. For more details, please review the [Security Documentation](docs/SECURITY.md).

## Contributing

Contributions are welcome. Please read the [Developer Guide](docs/DEVELOPER_GUIDE.md) to get started.