# apiops-orchestrator

APIOps Orchestrator in Python is built to compose, validate, plan and apply changes to APIs in the Sensedia API Management using artifacts (e.g. OpenAPI). The code is following Hexagonal Architecture principles (adapters, application, domain, infrastructure).

> Status: In Progress

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [How to Run](#how-to-run)
- [Folder Structure](#folder-structure)
- [Tech Stack](#tech-stack)
- [Contributors](#contributors)

## Overview

The APIOps Orchestrator is a Python tool for composing, validating and processing API Artifacts (e.g. OpenAPI) for the Sensedia API Management. Currently the project runs as a script that requires manual configuration to validate an API repository structure. The Command-Line Interface (CLI) was temporarily disabled to focus on the development of the core business logic.

## Features

- **Structure Validation:** Verify if the artifacts folder (`artifacts`) in an API repository follows the predefined folder and file structure rules.
- **File Importing:** List all the file paths within the (`artifacts`) folder for future processing.

## How To Run

### Requirements
- Python 3.10+
- Poetry (Dependency manager)

### 1. Setup

1.  **Install Poetry** (In case you haven't already):
    Follow the official instalation guide for your OS [here](https://python-poetry.org/docs/#installation).

2.  **Clone the repository** (In case you haven't already):
    ```bash
    git clone https://bitbucket.org/sensedia/apiops-orchestrator
    cd apiops-orchestrator
    ```

3.  **Install project dependencies**:
    Poetry will automatically create a virtual environment and install all dependencies.
    ```bash
    poetry install
    ```

### 2. Configuration

Before running, you **must** configure the path to the API repository that will be processed.

1.  **Environment Variables (.env)**
    Create a `.env` file in the project root, copying the content of `.env.example`. This file will be used to set the environment variables required by the orchestrator.

2.  Open `src/apiops_orchestrator/main.py`.
3.  Find and edit `repo_cep` so it points to the **absolut path** of your local API repository (ex: `api-repo-cep`).
    ```python
    repo_cep = Path(
        r"C:\caminho\absoluto\para\seu\api-repo-cep"  # Update this to your local repository path.
    )
    ```

### 3. Running the code

Run the script from the project root:
```bash
poetry run python src/apiops_orchestrator/main.py
```
The script will print the location of the artifacts folder, validate its structure and list the files found.

### Tests

To run the unit tests:
```bash
pytest
```

## Folder Structure
- `src/apiops_orchestrator/main.py` — Main orchestration script entry point.
- `src/apiops_orchestrator/config/settings.py` — Configuration and environment variables.
- `src/apiops_orchestrator/adapters/*` — Inbound/outbound adapters
- `src/apiops_orchestrator/application/*` — Application use cases and services.
- `src/apiops_orchestrator/domain/*` — Domain models, ports, and services.
- `src/apiops_orchestrator/infrastructure/*` — Infrastructure integrations.
- `tests/unit/...` — Unit tests.

## Tech Stack
- Python 3.10+
- Pydantic Settings (environment configuration/.env)
- Pytest (testing)
- Poetry (dependency management)

## Contributors
- Augusto
- Danilo Amaral
- Paulo de Oliveira
- Matheus Alves Giroto
- Alisson Lopes
- Luiza Silva
- Rapha Santos

---
Check also `CHANGELOG.md` for the project's changing history.

