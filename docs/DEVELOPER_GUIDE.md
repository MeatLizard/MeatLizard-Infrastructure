# Developer Guide

This guide provides instructions for setting up a development environment for the MeatLizard AI Chat System.

## Prerequisites

- Python 3.11+
- Docker
- Docker Compose
- A Discord account and a Discord server where you have admin privileges

## Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/meat-lizard.git
    cd meat-lizard
    ```

2.  **Create a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the dependencies:**
    ```bash
    pip install -r server/requirements.txt
    pip install -r client/client_bot/requirements.txt
    ```

4.  **Set up the environment variables:**
    -   Copy the `.env.example` file to `.env`.
    -   Fill in the required values in the `.env` file.

5.  **Start the database and Redis:**
    ```bash
    docker-compose up -d
    ```

6.  **Run the database migrations:**
    ```bash
    alembic -c server/alembic.ini upgrade head
    ```

7.  **Start the web server and server-bot:**
    ```bash
    python server/run_web_server.py
    ```

8.  **Start the client-bot:**
    ```bash
    python client/client_bot/run.py
    ```

## Running the Tests

To run the tests, use the following command:
```bash
pytest
```