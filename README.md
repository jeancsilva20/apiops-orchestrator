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

The APIOps Orchestrator is a Python tool for composing, validating, and processing API Artifacts (e.g., OpenAPI) for Sensedia API Management. It provides a Command-Line Interface (CLI) to automate the lifecycle of API revisions and deployments.

## Features

- **Structure Validation:** Verifies if the artifacts folder follows the predefined folder and file structure rules.
- **Schema Validation:** Validates YAML artifacts against their respective JSON schemas to ensure data integrity.
- **API Conversion:** Composes and converts YAML-based artifacts into a full API JSON model.
- **Revision Management:** Automates the creation of new API revisions in the Sensedia API Manager.
- **Deployment Automation:** Deploys API revisions to specific environments (e.g., Sandbox, Production).
- **YAML Versioning:** Generates and synchronizes local YAML files from the API JSON state.

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

Before running, you **must** configure the path to the API repository and other credentials.

1.  **Environment Variables (.env)**
    Create a `.env` file in the project root, copying the content of `.env.example`. This file will be used to set the environment variables required by the orchestrator.

2.  **API Repository Path**
    By default, the orchestrator looks for the API repository in the `./external-repo` folder. You can change this by setting the `API_REPO_FOLDER` variable in your `.env` file:
    ```env
    API_REPO_FOLDER="C:\path\to\your\api-repo"
    ```

3.  **Authentication & API Info**
    Ensure the following variables are set in your `.env` to allow communication with the Sensedia API Manager:
    - `OAUTH_CLIENT_ID`: Your API Manager user ClientId.
    - `OAUTH_CLIENT_SECRET`: Your API Manager user ClientSecret
    - `API_ID`: The ID of the API you are managing.
    - `ENVIRONMENT_ID`: The ID of the deployment environment.

### 3. Running the code

The orchestrator uses a CLI with the following commands:

**Create a new Revision:**
Validates the repository structure, validates artifacts against schemas, generates the API JSON, and creates a new revision in the Sensedia API Manager.
```bash
poetry run python src/apiops_orchestrator/main.py sen create revision
```

**Deploy a Revision:**
Generates the API JSON, performs the deployment to the configured environment, and synchronizes local YAML files.
```bash
poetry run python src/apiops_orchestrator/main.py sen deploy
```

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

