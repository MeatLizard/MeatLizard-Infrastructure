# Developer Guide

This guide provides instructions for developers working on the MeatLizard AI Platform. It covers setting up a development environment, coding conventions, and the testing process.

## 1. Getting Started: Dev Environment

We use Docker and `docker-compose` to manage the development environment for the server-side components.

### 1.1. Prerequisites

-   Docker
-   `docker-compose`
-   Python 3.11+ on your local machine for running tests and scripts.
-   An editor with support for Python, `black` for formatting, and `ruff` for linting.

### 1.2. Server-Side Setup

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-username/MeatLizard-Infrastructure.git
    cd MeatLizard-Infrastructure
    ```

2.  **Create Environment Files**:
    -   Copy the example `.env.example` to `.env`.
    -   Review the `.env` file and fill in the required secrets, especially the Discord bot tokens and the `PAYLOAD_ENCRYPTION_KEY`. You can generate a new encryption key with:
        ```bash
        openssl rand -hex 32
        ```

3.  **Build and Start Services**:
    ```bash
    docker-compose up --build -d
    ```
    This will build the Docker images for the FastAPI app, the `server-bot`, and start the PostgreSQL and Redis containers.

4.  **Run Database Migrations**:
    -   The database migrations are handled by Alembic. To apply the latest migrations, run:
    ```bash
    docker-compose exec web alembic upgrade head
    ```

5.  **Accessing Services**:
    -   **FastAPI App**: `http://localhost:8000`
    -   **FastAPI Docs**: `http://localhost:8000/docs`
    -   **PostgreSQL**: `localhost:5432`
    -   **Redis**: `localhost:6379`

## 2. Coding Conventions

-   **Formatting**: All Python code is formatted with `black`. Please run it before committing your changes.
    ```bash
    black .
    ```
-   **Linting**: We use `ruff` for linting. It's fast and comprehensive.
    ```bash
    ruff check .
    ```
-   **Typing**: All new code should be fully type-hinted using Python 3.11+ syntax.
-   **Commit Messages**: Follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification.
    -   Example: `feat: add user authentication to web interface`
    -   Example: `fix: correct payload decryption error in server-bot`
    -   Example: `docs: update architecture diagram`

## 3. Project Structure

-   `/server/web`: The FastAPI application.
-   `/server/server_bot`: The main `discord.py` bot for orchestration.
-   `/client_bot`: The `discord.py` bot for `llama.cpp` inference.
-   `/shared_lib`: Python code shared between the server components (e.g., database models, encryption utilities).
-   `/infra`: Dockerfiles and `docker-compose.yml`.
-   `/tests`: All unit and integration tests.

## 4. Testing Plan

A robust testing strategy is crucial for this project. The testing plan is divided into three main categories.

### 4.1. Unit Tests

-   **Location**: `/tests` directory, mirroring the project structure.
-   **Framework**: `pytest`
-   **Scope**:
    -   **Database Models**: Test the logic and relationships in `shared_lib/models.py`.
    -   **Encryption**: Verify the correctness of the AES-256-GCM encryption and decryption in `shared_lib/encryption.py`.
    -   **API Endpoints**: Test the logic of individual FastAPI endpoints with mock data and a test database.
    -   **Llama.cpp Wrapper**: Test the command-building logic and subprocess handling (with a mock executable).
-   **How to Run**:
    ```bash
    # Make sure you have the dev dependencies installed
    pip install -r requirements-dev.txt

    # Run all tests
    pytest
    ```

### 4.2. Integration Tests

-   **Location**: `/tests/integration`
-   **Scope**:
    -   **Full Message Relay**: Test the entire flow from the FastAPI app -> `server-bot` -> `client-bot` (in echo mode) -> `server-bot` -> FastAPI. This is the most critical integration test. It will use a live test Discord server.
    -   **Database & API**: Test that the API correctly reads from and writes to the test database.
    -   **Slash Commands**: Test the interaction between the `server-bot` and the Discord API for slash commands.

### 4.3. Load Tests

-   **Framework**: A tool like `locust` can be used.
-   **Scope**:
    -   **API Stress Test**: Hammer the FastAPI `/send` endpoint to measure requests per second and identify bottlenecks.
    -   **Inference Throughput**: Send a continuous stream of requests to the `client-bot` to measure its maximum sustainable tokens/second.

## 5. Dependencies

-   Server-side Python dependencies are managed in `server/requirements.txt`.
-   Client-side Python dependencies are in `client_bot/requirements.txt`.
-   When adding a new dependency, add it to the appropriate file and rebuild the Docker image if necessary.
