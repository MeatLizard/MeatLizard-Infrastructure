# GEMINI.MD: AI Collaboration Guide

This document provides essential context for AI models interacting with this project. Adhering to these guidelines will ensure consistency and maintain code quality.

## 1. Project Overview & Purpose

* **Primary Goal:** This is a multi-service platform that provides a suite of services including URL shortening, pastebin, media hosting with transcoding, and an AI chat system.
* **Business Domain:** The project is a general-purpose platform for content creation and sharing.

## 2. Core Technologies & Stack

* **Languages:** Python 3.10
* **Frameworks & Runtimes:** FastAPI, Celery
* **Databases:** PostgreSQL, Redis
* **Key Libraries/Dependencies:** SQLAlchemy, Pydantic, ffmpeg-python, SpeechRecognition
* **Package Manager(s):** pip

## 3. Architectural Patterns

* **Overall Architecture:** The project follows a service-oriented architecture, with a central FastAPI application providing the API and a Celery worker for background tasks.
* **Directory Structure Philosophy:**
    * `/server`: Contains all primary source code.
        * `/web`: Contains the FastAPI web application.
            * `/app`: Contains the core application logic, including services and models.
            * `/alembic`: Contains the database migration scripts.
        * `/background_worker.py`: Defines the Celery tasks.
        * `/celery_app.py`: Configures the Celery application.
    * `/shared_lib`: Contains shared utilities and models.
    * `/tests`: Contains all unit and integration tests.
    * `/infra`: Contains the Docker Compose configuration.

## 4. Coding Conventions & Style Guide

* **Formatting:** The project follows the PEP 8 style guide.
* **Naming Conventions:**
    * `variables`, `functions`: snake_case (`my_variable`)
    * `classes`, `components`: PascalCase (`MyClass`)
    * `files`: snake_case (`my_service.py`)
* **API Design:** The API follows RESTful principles. Endpoints are plural nouns. Uses standard HTTP verbs (GET, POST, PUT, DELETE). JSON for request/response bodies.
* **Error Handling:** Uses FastAPI's exception handling to return appropriate HTTP status codes.

## 5. Key Files & Entrypoints

* **Main Entrypoint(s):** `server/web/app/main.py`
* **Configuration:** `.env`
* **CI/CD Pipeline:** Not present.

## 6. Development & Testing Workflow

* **Local Development Environment:** Use `docker-compose up -d` to start the database and Redis. Use `uvicorn server.web.app.main:app --reload` to start the web server. Use `celery -A server.celery_app worker --loglevel=info` to start the Celery worker.
* **Testing:** Run tests via `pytest`. New code requires corresponding unit and integration tests.
* **CI/CD Process:** Not present.

## 7. Specific Instructions for AI Collaboration

* **Contribution Guidelines:** Not present.
* **Infrastructure (IaC):** Changes to files in the `/infra` directory modify the Docker Compose configuration and must be carefully reviewed.
* **Security:** Be mindful of security. Do not hardcode secrets or keys. Ensure any changes to authentication logic are secure and vetted.
* **Dependencies:** When adding a new dependency, add it to the appropriate `requirements.txt` file.
* **Commit Messages:** Follow the Conventional Commits specification (e.g., `feat:`, `fix:`, `docs:`).