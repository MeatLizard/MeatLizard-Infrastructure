# Testing Plan

This document outlines the comprehensive testing strategy for the MeatLizard AI Platform to ensure its reliability, security, and performance.

## 1. Testing Philosophy

-   **Automation First**: All tests that can be automated, should be. This is crucial for CI/CD.
-   **Pyramid Approach**: The strategy follows the testing pyramid: a large base of fast unit tests, a smaller layer of integration tests, and a very small number of manual or end-to-end tests.
-   **Isolation**: Tests should be independent and not rely on the state of previous tests. Test databases and mocks should be used extensively.

## 2. Levels of Testing

### 2.1. Unit Tests

-   **Goal**: To verify that individual components (functions, classes) work correctly in isolation.
-   **Framework**: `pytest`
-   **Location**: `/tests`
-   **Key Areas**:
    -   `shared_lib/encryption.py`:
        -   Test that a payload encrypted with a key can be decrypted with the same key.
        -   Test that decryption fails with a different key.
        -   Test handling of non-string and empty inputs.
    -   `shared_lib/models.py`:
        -   Test model creation and relationships.
        -   Test data validation (e.g., a message must be linked to a session).
    -   `server/web/app/main.py`:
        -   Test each API endpoint's logic using FastAPI's `TestClient`.
        -   Mock database sessions and dependencies.
        -   Test for correct HTTP status codes (200, 201, 404, 422, etc.).
    -   `client_bot/llama_cpp_wrapper.py`:
        -   Test the command-line argument construction logic.
        -   Mock the `subprocess.Popen` call to verify that the wrapper attempts to call `llama.cpp` with the correct flags for different inputs.
    -   `server/server_bot/bot.py`:
        -   Test individual cogs or functions in isolation.
        -   Mock the Discord API (`discord.py.mocks`) to test command logic without connecting to Discord.

### 2.2. Integration Tests

-   **Goal**: To verify that different components of the system work together as expected.
-   **Framework**: `pytest` with `pytest-asyncio`.
-   **Location**: `/tests/integration`
-   **Key Scenarios**:
    -   **Full Message Relay (Mocked LLM)**:
        1.  An API call is made to the `/sessions/{id}/messages` endpoint.
        2.  The FastAPI app writes to the test database.
        3.  The `server-bot` picks up the request.
        4.  The `server-bot` encrypts and sends a message to a real, dedicated test Discord server.
        5.  A test version of the `client-bot` (running in "echo mode") receives, decrypts, re-encrypts, and sends back the message.
        6.  The `server-bot` receives, decrypts, and notifies the web server.
        7.  Verify the final state in the database is correct.
    -   **Database Integrity**:
        -   Test that API actions are correctly persisted in the test PostgreSQL database.
        -   Run tests within transactions that are rolled back after each test to ensure a clean state.
    -   **Session Creation Flow**:
        -   Test the full flow from a `/api/v1/sessions` call to the `server-bot` creating a private channel in the test Discord server.

### 2.3. End-to-End (E2E) Tests

-   **Goal**: To simulate a real user's workflow from start to finish. These are often manual but can be automated with tools like Selenium.
-   **Key Scenarios**:
    -   **Web UI to AI Response**:
        1.  Manually open the web UI in a browser.
        2.  Start a new chat.
        3.  Send a message.
        4.  Verify that a response from the actual `llama.cpp` model appears in the UI.
        5.  Verify the new private channel was created in Discord.
    -   **Discord User to AI Response**:
        1.  Use the `/ai start` command in Discord.
        2.  Send a message in the newly created channel.
        3.  Verify a response from the AI is posted in the channel.

### 2.4. Load & Performance Tests

-   **Goal**: To understand the system's limits and identify performance bottlenecks.
-   **Framework**: `locust` or `k6`.
-   **Key Scenarios**:
    -   **API Throughput**: How many messages per second can the FastAPI app handle before response times degrade?
    -   **Inference Speed**: What is the average tokens/second for the `client-bot` under sustained load?
    -   **Database Performance**: Monitor query times and connection pooling during a load test.

## 3. Continuous Integration

-   A CI pipeline (e.g., using GitHub Actions) should be set up to:
    1.  Run `black` and `ruff` on every push.
    2.  Run all unit and integration tests on every push to the `main` branch or on pull requests.
    3.  Build the Docker images to ensure they don't have issues.
