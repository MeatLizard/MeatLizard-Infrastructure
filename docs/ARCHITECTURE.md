# Architecture

This document provides a detailed overview of the MeatLizard AI Platform's architecture.

## 1. System Components

The system is composed of three primary, decoupled components:

1.  **Web Server (FastAPI):** A high-performance Python web server built with FastAPI. It serves the entire frontend user interface (HTML, CSS, JS) and handles user interaction via WebSockets. It is responsible for authentication, session management, and acting as the primary entry point for web users.

2.  **Server-Bot (discord.py):** A Python-based Discord bot that acts as the central orchestrator. It manages the Discord guild, creates private channels for chat sessions, handles all slash commands, logs metrics to the database, saves transcripts to S3, and manages user permissions. It communicates with the FastAPI server via internal, asynchronous message queues.

3.  **Client-Bot (discord.py):** A dedicated Python-based Discord bot designed to run on a machine with a powerful GPU (specifically macOS with Apple Metal support). Its sole responsibility is to listen for encrypted prompts from the Server-Bot, perform LLM inference using a local `llama.cpp` instance, and send the encrypted response back.

## 2. Data Flow & Communication

The data flow is designed to be asynchronous and secure, ensuring that user prompts and AI responses are handled efficiently and privately.

```
                               +-------------------------+
                               |      FastAPI Server     |
                               | (Web UI & WebSockets)   |
                               +-----------+-------------+
                                           | (Internal Queues)
+------------------------------------------+-------------------------------------------+
|                                          |                                           |
|                                          v                                           |
|  +-------------------------+     +-------+----------+      +-----------------------+ |
|  |     PostgreSQL DB       |     |  Server-Bot      |      |      Redis            | |
|  | (Users, Sessions, Logs) | <-->| (Orchestrator)   | <--> | (Rate Limits, Cache)  | |
|  +-------------------------+     +-------+----------+      +-----------------------+ |
|                                          |                                           |
|                                          | (Discord API - Encrypted Messages)        |
|                                          |                                           |
|                                          v                                           |
|                                +---------+--------+                                  |
|                                |   Client-Bot     |                                  |
|                                | (LLM Inference)  |                                  |
|                                +-------+----------+                                  |
|                                        | (Subprocess Call)                           |
|                                        v                                             |
|                                +-------+----------+                                  |
|                                |    llama.cpp     |                                  |
|                                | (Apple Metal MPS)|                                  |
|                                +------------------+                                  |
+--------------------------------------------------------------------------------------+
```

**Step-by-Step Flow:**

1.  **Session Start (Web):** A user connects to the FastAPI server via WebSocket. The server creates a unique session ID and a dedicated `asyncio.Queue` for this session, storing it in a shared dictionary (`app.state.response_queues`).
2.  **Request to Bot:** The FastAPI server places a `create_session` message onto a global request queue (`app.state.message_queue`).
3.  **Channel Creation:** The Server-Bot, running in a separate thread, picks up the message. It connects to the Discord API and creates a new, private text channel visible only to the bot and administrators.
4.  **Prompt Handling:** The user sends a prompt over the WebSocket. The FastAPI server encrypts it and places it on the request queue with the corresponding `session_id`.
5.  **Relay to Client:** The Server-Bot retrieves the encrypted prompt and sends it as a message to the appropriate private Discord channel.
6.  **LLM Inference:** The Client-Bot, listening in the channel, receives the message. It decrypts the content, passes the prompt to its local `llama.cpp` instance for processing, and waits for the response.
7.  **Response Relay:** The Client-Bot encrypts the AI's response and sends it back to the Discord channel.
8.  **Return to Web UI:** The Server-Bot sees the Client-Bot's message, decrypts it, finds the correct session-specific response queue from the shared state, and places the plain-text response into it.
9.  **Display to User:** The FastAPI server, which was awaiting a message on the response queue, immediately receives the response and sends it over the WebSocket to the user's browser.

## 3. Storage

-   **PostgreSQL:** The primary relational database for storing persistent data such as users, sessions, messages, audit logs, and metrics.
-   **Redis:** Used for caching, rate limiting, and potentially as a more robust message queue in a scaled-up deployment.
-   **S3-Compatible Storage:** Used for storing large objects, specifically chat transcripts and database backups.
