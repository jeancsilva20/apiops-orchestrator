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

The APIOps Orchestrator is a Python tool for composing, validating and processing API Artifacts (e.g. OpenAPI) for the Sensedia API Management. It ships with a CLI (`sen`) for authentication and API listing, and also runs the legacy artifact validation flow as a script.

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

# 2. Copy src/apiops_orchestrator/.sen.example to src/apiops_orchestrator/.sen,
#    then fill in the three mandatory keys (they are ONLY read from .sen, not .env):
#    SEN_CREDENTIALS=<blob from step 1>
#    AUTH_HOST=https://api-consulting.sensedia.com
#    AUTH_LOGIN_PATH=/cli-2/orq-auth/v1/oauth2/token

# 3. Run:
poetry run sen login
```

> **Nota (console script `sen`):** o binário `sen` é criado a partir de
> `[tool.poetry.scripts]` no `pyproject.toml` quando o próprio pacote é
> instalado no ambiente — via Poetry (`poetry install`) **ou** via pip
> (`pip install -e .`, já contemplado no setup da Opção A).
> O `sen --version` degrada graciosamente para uma versão estática caso a
> metadata do pacote não esteja disponível. Em ambos os ambientes, a
> alternativa `python src/apiops_orchestrator/main.py sen <comando>`
> (ou `poetry run python ...`) continua funcionando e aceita os mesmos comandos.

The credential file lives in the **package directory** (`src/apiops_orchestrator/.sen`, git-ignored) — see
[`docs/features/sen-login.md`](docs/features/sen-login.md).

The session file is stored at the **project root** as `.sen_session` (hidden, owner-only, git-ignored — see ADR 0006).
Full behavior (exit codes, session file and privacy) is documented in
[`docs/features/sen-login.md`](docs/features/sen-login.md).

## How To Run

### Requirements
- Python 3.12+ (with `pip`)
- Poetry (optional — only if you prefer the Poetry workflow)

### 1. Setup

#### Option A — pip (no Poetry needed)

1.  **Clone the repository** (In case you haven't already):
    ```bash
    git clone https://bitbucket.org/sensedia/apiops-orchestrator
    cd apiops-orchestrator
    ```

2.  **Bootstrap the virtual environment** (creates `.venv\`, installs dependencies from `requirements.txt` — pinned to the versions validated in `poetry.lock` — and installs the package itself in editable mode):
    ```powershell
    powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
    ```

    Or manually, if you prefer (same effect):
    ```powershell
    python -m venv .venv
    .\.venv\Scripts\pip install -r requirements.txt
    .\.venv\Scripts\pip install -e .
    ```

    > Why `pip install -e .`? The project uses a **src-layout**: running
    > `python src\...main.py` only resolves the internal imports if the package
    > is installed in the environment (same reason `poetry install` works).
    > It also generates the `sen` binary and the version metadata.

3.  **Development only** (tests/linters/docs — equivalent to `poetry install` with dev group):
    ```powershell
    .\.venv\Scripts\pip install -r requirements-dev.txt
    ```
    (or rerun the setup script with the `-Dev` flag)

#### Option B — Poetry

```powershell
poetry install
```

The Poetry flow keeps using `pyproject.toml` + `poetry.lock` as before — untouched.

Both options produce an isolated environment; pick ONE of them per machine/clone.

All commands below use the local interpreter directly:
```powershell
.\.venv\Scripts\python.exe
```

### 2. Configuration (Optional for tests)

This step is optional if you only want to run tests. Before running the main script, you can configure the path to the API repository that will be processed.

1.  **Environment Variables (.env)**
    Create a `.env` file in the project root, copying the content of `.env.example`. This file will be used to set the environment variables required by the orchestrator.

2.  Open `src/apiops_orchestrator/main.py`.
3.  Find and edit `repo_path` (around line 51) so it points to the **absolute path** of your local API repository (ex: `api-repo-cep`).
    ```python
    repo_path = Path(
        r"C:\caminho\absoluto\para\seu\api-repo-cep"  # Update this to your local repository path.
    )
    ```

### 3. Running the code

Run the script from the project root:
```powershell
.\.venv\Scripts\python.exe src\apiops_orchestrator\main.py
```
The script will print the location of the artifacts folder, validate its structure and list the files found.

Equivalent with the Poetry environment:
```powershell
poetry run python src/apiops_orchestrator/main.py
```

### Tests

Ensure you have followed the **Setup** steps first. To run the unit tests:
```powershell
.\.venv\Scripts\python.exe -m pytest
```

Equivalent with the Poetry environment:
```powershell
poetry run pytest
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
- Python 3.12+
- Pydantic Settings (environment configuration/.env)
- Pytest (testing)
- Dependency management: pip + requirements.txt (standard) or Poetry (optional)

## Contributors
- Augusto
- Danilo Amaral
- Paulo de Oliveira
- Matheus Alves Giroto
- Alisson Lopes
- Luiza Silva
- Jean Silva
- Isaac Machado

---
Check also `CHANGELOG.md` for the project's changing history.

