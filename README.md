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

- **Authentication (`sen login`):** Authenticate against the Orchestrator Auth API and store the session locally (details: `docs/features/sen-login.md`).
- **Structure Validation:** Verify if the artifacts folder (`artifacts`) in an API repository follows the predefined folder and file structure rules.
- **File Importing:** List all the file paths within the (`artifacts`) folder for future processing.

## CLI Commands

### `sen login`

Authenticates the user against the Orchestrator Auth API and saves the session locally for subsequent executions.

```powershell
# 1. Generate the credential blob (Base64 of client_id:secret — no "Basic" prefix):
[Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("<client_id>:<secret>"))

# 2. Set it in the .env at the project root (see .env.example), then run:
.\.venv\Scripts\python.exe src\apiops_orchestrator\main.py sen login
```

The session file is stored at the **project root** as `.sen_session` (hidden, owner-only, git-ignored — see ADR 0006).
Full behavior (credential sources, endpoint variables, exit codes, session file and privacy) is documented in
[`docs/features/sen-login.md`](docs/features/sen-login.md).

## How To Run

### Requirements
- Python 3.10+

### 1. Setup

1.  **Clone the repository** (In case you haven't already):
    ```bash
    git clone https://bitbucket.org/sensedia/apiops-orchestrator
    cd apiops-orchestrator
    ```

2.  **Bootstrap the virtual environment** (creates `.venv\` and installs all dependencies from `pyproject.toml`, no Poetry needed):
    ```powershell
    powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
    ```

    All commands below use the local interpreter directly:
    ```powershell
    .\.venv\Scripts\python.exe
    ```

### 2. Configuration (Optional for tests)

This step is optional if you only want to run tests. Before running the main script, you can configure the path to the API repository that will be processed.

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
```powershell
.\.venv\Scripts\python.exe src\apiops_orchestrator\main.py
```
The script will print the location of the artifacts folder, validate its structure and list the files found.

### Tests

Ensure you have followed the **Setup** steps first. To run the unit tests:
```powershell
.\.venv\Scripts\python.exe -m pytest
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
- venv + pip (dependency management, installed from `pyproject.toml`)
- Pydantic Settings (environment configuration/.env)
- Pytest (testing)

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

