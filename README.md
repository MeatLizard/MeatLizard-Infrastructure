# MeatLizard AI Chat System

This project is a sophisticated, two-part AI chat system designed for both web and Discord-based interaction. It features a powerful FastAPI backend, a Discord server-bot for management, and a dedicated client-bot for LLM inference.

## Key Features

- **Dual Interface:** Access AI chat sessions from a web UI or through Discord.
- **Private & Secure:** Each chat session is conducted in a private Discord channel.
- **High-Performance Inference:** The client-bot leverages `llama.cpp` with Apple Metal (MPS) for efficient, local LLM inference.
- **Robust & Scalable:** The system is built with a production-ready architecture, using PostgreSQL, Redis, and S3 for data storage and caching.
- **Comprehensive Admin Features:** The server-bot provides a suite of admin commands for managing the system, including session control, metrics, and backups.

## Getting Started

To get started with the MeatLizard AI Chat System, please refer to the following documents:

- **[Architecture](docs/ARCHITECTURE.md):** A detailed overview of the system's design and data flow.
- **[Developer Guide](docs/DEVELOPER_GUIDE.md):** Instructions for setting up a development environment and contributing to the project.
- **[Deployment Guide](docs/DEPLOYMENT.md):** Instructions for deploying the system to a production environment.
