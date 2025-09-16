# Project Summary

This project, codenamed "MeatLizard," is a sophisticated, multi-part AI chat system designed for production use. It integrates a web-based chat interface with a powerful Discord bot ecosystem, leveraging both server-side and client-side AI inference capabilities.

## Core Components

1.  **FastAPI Web Server**: Provides a ChatGPT-like user interface for web users, handles session management, and serves as the central API for the entire system.
2.  **Server-Side Discord Bot (`server-bot`)**: The orchestrator of the Discord guild. It manages user sessions, creates private chat channels, handles permissions, triggers backups, logs metrics, and performs content moderation.
3.  **Client-Side Discord Bot (`client-bot`)**: A specialized bot designed to run on dedicated macOS hardware with Apple Silicon. It connects to the Discord gateway and performs all heavy-duty LLM inference using `llama.cpp` accelerated by the Metal Performance Shaders (MPS) framework.
4.  **PostgreSQL Database**: The primary data store for all persistent information, including user data, chat sessions, message history, transcripts, system configurations, and metrics.
5.  **Redis**: Used as a high-speed cache for rate limiting, session data, and other ephemeral information.
6.  **S3-Compatible Storage**: Provides durable, long-term storage for chat transcripts and database backups.

## Key Features

-   **Hybrid Chat**: Users can initiate conversations from either the web interface or directly within Discord. Web users are transparently represented in private Discord channels for administrative oversight.
-   **Private & Secure Sessions**: Each chat session is isolated in a new, private Discord channel with strict permissions.
-   **Encrypted Communication**: All communication between the `server-bot` and `client-bot` is end-to-end encrypted using AES-256-GCM to protect the contents of prompts and responses.
-   **Graceful Fallback**: If the `client-bot` (and its powerful LLM) goes offline, the system can gracefully degrade to a lightweight, server-side Markov chain generator to maintain service availability.
-   **Comprehensive Admin Controls**: Administrators have a full suite of slash commands to manage the system, including enabling/disabling requests, transferring sessions, viewing metrics, and initiating backups.
-   **Detailed Metrics**: The system collects and displays key performance indicators, such as uptime, tokens per second, and GPU utilization, in a dedicated `#ai-metrics` channel and the central database.
-   **Robust Data Management**: Transcripts are automatically generated upon session closure, archived to S3, and made available to administrators and (optionally) users. The database is backed up regularly.
-   **Security-First Design**: The architecture incorporates TLS, environment-based secrets management, strict Discord permissions, and content moderation filters.

This project aims to provide a scalable, secure, and feature-rich platform for hosting a private AI chat service.