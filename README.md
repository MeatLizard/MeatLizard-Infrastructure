# MeatLizard AI Platform

This project is a sophisticated, two-part AI chat system designed for both web and Discord-based interaction. It features a powerful FastAPI backend, a Discord server-bot for management, and a dedicated client-bot for LLM inference.

The platform provides a suite of services including a chat interface, pastebin, URL shortener, file storage, and a fully-featured video player, all presented with a consistent, retro-inspired dark-mode theme.

## Key Features

-   **Multi-Service Platform:** A unified web interface for AI chat, pastebin, URL shortening, file storage, and video playback.
-   **Dual Interface:** Access AI chat sessions from the web UI or through Discord slash commands.
-   **Private & Secure:** Each chat session is conducted in a private Discord channel, with end-to-end encryption for all messages.
-   **High-Performance Inference:** The client-bot leverages `llama.cpp` with Apple Metal (MPS) for efficient, local LLM inference.
-   **Robust & Scalable:** The system is built with a production-ready architecture, using PostgreSQL for data, Redis for caching/rate-limiting, and S3-compatible storage for transcripts and backups.
-   **Comprehensive Admin Features:** The server-bot provides a suite of admin commands for managing the system, including session control, metrics, and backups.

## Project Documentation

For detailed information about the system, please refer to the following documents in the `/docs` directory:

-   **[ARCHITECTURE.md](docs/ARCHITECTURE.md):** A detailed overview of the system's design, components, and data flow.
-   **[API_SCHEMA.md](docs/API_SCHEMA.md):** Formal specification of the JSON schemas used for communication.
-   **[DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md):** Instructions for setting up a development environment.
-   **[DEPLOYMENT.md](docs/DEPLOYMENT.md):** Step-by-step instructions for deploying the system to a production environment.
-   **[ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md):** A guide to the available slash commands for users and administrators.
-   **[SECURITY.md](docs/SECURITY.md):** An overview of the security measures implemented in the system.
-   **[BACKUPS.md](docs/BACKUPS.md):** Procedures for backing up and restoring system data.
-   **[PROMPT_LIBRARY.md](docs/PROMPT_LIBRARY.md):** A collection of preset prompts for guiding the AI.
-   **[TESTING_PLAN.md](docs/TESTING_PLAN.md):** The plan for ensuring the quality and stability of the system.