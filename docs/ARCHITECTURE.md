# System Architecture

This document provides a detailed overview of the MeatLizard AI Chat Platform's architecture, its components, and the flow of data through the system.

## 1. Architecture Diagram (Text-Based)

```
                               +-------------------------+
                               |   End User (Browser)    |
                               +-------------------------+
                                          | (HTTPS)
                                          v
+-------------------------------------------------------------------------------------+
|                                     SERVER SIDE                                     |
|                                                                                     |
|  +-----------------------+      +-----------------------+      +------------------+ |
|  |   FastAPI Web App     |<---->|      PostgreSQL       |<---->|      Redis       | |
|  | (Session Mgmt, UI)    |      | (Users, Sessions,     |      | (Rate Limiting,  | |
|  +-----------------------+      |  Messages, Config)    |      |   Cache)         | |
|           ^                     +-----------------------+      +------------------+ |
|           |                                |                     ^                  |
|           v                                v                     |                  |
|  +-----------------------+      +-----------------------+      |                  |
|  |  Server Discord Bot   |      |      S3 Storage       |      |                  |
|  |   (Orchestrator)      |<---->| (Transcripts, Backups)|      |                  |
|  +-----------------------+      +-----------------------+      |                  |
|           |                                                      |                  |
|           | (Discord Gateway API, Encrypted JSON Payload)        |                  |
|           v                                                      |                  |
+-------------------------------------------------------------------------------------+
           |
           |
+-------------------------------------------------------------------------------------+
|                                    CLIENT SIDE                                      |
|                                  (macOS Hardware)                                   |
|                                                                                     |
|  +-----------------------+                                                        |
|  |  Client Discord Bot   |                                                        |
|  | (Inference Handler)   |                                                        |
|  +-----------------------+                                                        |
|           |                                                                         |
|           v (Local Subprocess)                                                      |
|  +-----------------------+                                                        |
|  |      llama.cpp        |                                                        |
|  | (LLM Inference, MPS)  |                                                        |
|  +-----------------------+                                                        |
|                                                                                     |
+-------------------------------------------------------------------------------------+
```

## 2. Component Breakdown

### Server-Side Components

-   **FastAPI Web App**: The primary user-facing component. It's a Python web application built with FastAPI that serves a ChatGPT-like single-page application.
    -   **Responsibilities**: User authentication, session creation and management, serving the web UI, and providing an API for sending and receiving messages.
-   **Server Discord Bot (`server-bot`)**: A Python application using `discord.py`. It acts as the central nervous system of the chat platform.
    -   **Responsibilities**:
        -   Receiving new session requests from the FastAPI app.
        -   Creating and managing private Discord channels for each chat session.
        -   Enforcing user permissions and rate limits.
        -   Relaying messages securely to the `client-bot`.
        -   Handling slash commands for administration.
        -   Logging metrics to the database and the `#ai-metrics` channel.
        -   Orchestrating the creation of transcripts and backups.
-   **PostgreSQL Database**: A relational database that serves as the single source of truth for all persistent data.
    -   **Managed Data**: User accounts, chat sessions, individual messages, system configurations, and historical metrics.
-   **Redis**: An in-memory data store used for caching and high-speed operations.
    -   **Responsibilities**: Rate limiting enforcement, caching of frequently accessed data, and temporary session storage.
-   **S3-Compatible Storage**: A cloud or self-hosted object storage solution.
    -   **Responsibilities**: Long-term, durable storage of chat transcripts (in JSON/CSV format) and regular database backups.

### Client-Side Components

-   **Client Discord Bot (`client-bot`)**: A specialized Python `discord.py` bot designed to run on a dedicated macOS machine with Apple Silicon.
    -   **Responsibilities**:
        -   Listening for encrypted message payloads from the `server-bot`.
        -   Decrypting payloads and validating requests.
        -   Calling the `llama.cpp` executable as a local subprocess with appropriate flags for Metal (MPS) GPU acceleration.
        -   Capturing the LLM's output.
        -   Encrypting the response and sending it back to the `server-bot`.
        -   Monitoring its own health and gracefully handling shutdowns (e.g., due to low battery).
-   **llama.cpp**: A high-performance C/C++ implementation for running LLaMA-family models.
    -   **Responsibilities**: Performing the actual LLM inference. It is configured to use Apple's Metal Performance Shaders for hardware acceleration.

## 3. Data Flow: A User's Message

This section describes the end-to-end journey of a single message from a web user.

1.  **User Sends Message**: The user types a message into the web UI and clicks "Send". The frontend makes an HTTPS POST request to a FastAPI endpoint (e.g., `/api/v1/sessions/{session_id}/send`).

2.  **FastAPI Processes Request**:
    -   The FastAPI app receives the request, authenticates the user, and validates the `session_id`.
    -   It retrieves session metadata (like the associated Discord channel ID) from the PostgreSQL database.
    -   It saves the user's message to the `messages` table in the database.

3.  **Relay to Server-Bot**:
    -   The FastAPI app forwards the message content and session metadata to the `server-bot`. (This can be done via an internal API call or a shared Redis queue).

4.  **Server-Bot Prepares Payload**:
    -   The `server-bot` receives the message.
    -   It constructs a JSON payload containing the `session_id`, a unique `request_id`, the user's prompt, and any model parameters (e.g., temperature).
    -   It encrypts this JSON payload using AES-256-GCM with a pre-shared secret key.

5.  **Transmission to Client-Bot**:
    -   The `server-bot` sends the encrypted payload as a message to the private Discord channel corresponding to the user's session. This message is often prefixed with a special character or format that the `client-bot` is programmed to recognize, ignoring all other messages.

6.  **Client-Bot Receives and Decrypts**:
    -   The `client-bot`, running on the macOS machine, sees the new message in the channel.
    -   It identifies it as an inference request, decrypts the payload using the shared secret, and validates its structure.

7.  **Inference with llama.cpp**:
    -   The `client-bot` invokes the `llama.cpp` binary as a subprocess.
    -   It passes the prompt from the payload to `llama.cpp`'s standard input and includes command-line arguments for the model path, context size, temperature, and MPS (`--mps`) flags.
    -   `llama.cpp` loads the model into the Apple Silicon GPU and performs inference.

8.  **Client-Bot Handles Response**:
    -   The `client-bot` captures the text output from `llama.cpp`'s standard output.
    -   It constructs a response JSON payload containing the original `request_id` and the generated text.
    -   It encrypts this response payload and sends it back to the same private Discord channel.

9.  **Server-Bot Processes Response**:
    -   The `server-bot` sees the encrypted response from the `client-bot`.
    -   It decrypts the payload and matches the `request_id` to the original request.
    -   It forwards the decrypted response text back to the FastAPI application.

10. **Final Delivery to User**:
    -   The FastAPI app receives the response.
    -   It saves the AI's message to the `messages` table in the database.
    -   It sends the response back to the user's browser, typically over a WebSocket connection or as the response to the initial POST request, where it is displayed in the UI.

## 4. Offline Fallback Flow

-   If the `server-bot` fails to get a response from the `client-bot` within a timeout period, it assumes the client is offline.
-   It can then either:
    1.  **Inform the User**: Send a message to the FastAPI app indicating that the AI is temporarily unavailable.
    2.  **Engage Fallback Model**: Generate a response using a simple, server-side Markov chain generator. This provides a degraded but still functional experience.
-   The choice of strategy is configurable.
