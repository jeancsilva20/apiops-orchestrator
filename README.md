# apiops-orchestrator


APIOps Orchestrator in Python is built to compose, validate, plan and apply changes to APIs in the Sensedia API Management using artifacts (e.g. OpenAPI). The code is following Hexagonal Architecture principles (adapters, application, domain, infrastructure).

> Status: In Progress

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [CLI Commands](#cli-commands)
- [Configuration](#configuration)
- [How to Run](#how-to-run)
- [Folder Structure](#folder-structure)
- [Tech Stack](#tech-stack)
- [Contributors](#contributors)

## Overview

The APIOps Orchestrator is a Python tool for composing, validating and processing API Artifacts (e.g. OpenAPI) for the Sensedia API Management. It ships as a CLI (`sen`) that authenticates against the Orchestrator Auth API and then talks to the Sensedia Manager to list, validate, publish and deploy APIs.

## Features

- **Authentication (`sen login`):** authenticates against the Orchestrator Auth API and stores the session locally.
- **Listing (`sen list api`):** lists the APIs and revisions visible in the Manager.
- **Governance score (`sen completeness`):** shows the completeness of an API revision.
- **Validation (`sen validate`):** validates the API repository and writes to the Draft revision to get the governance verdict.
- **Publishing (`sen publish`) and deployment (`sen deploy`):** pipeline-only operations against the target revision/environment.

## CLI Commands

Run `sen --help` or `sen <command> --help` for the authoritative option list. All commands accept `--output/-o` with `text` (default), `json` or `yaml`.

| Command | What it does | Notes |
|---|---|---|
| `sen login` | Authenticates and saves the session locally | Required before every other command |
| `sen list api` | Lists APIs in the Manager | `--id`, `--query`, `--limit`, `--offset`, `--all`, `--revisions/-r` |
| `sen completeness` | Completeness of an API revision | `--id`, `--revision`, `--score-only` |
| `sen validate` | Validates the repository and writes to Draft | `--repo` (default: current directory) |
| `sen publish` | Publishes to the environment revision | Pipeline only (`EXECUTION_MODE=pipeline`) |
| `sen deploy` | Deploys the revision to the environment | Pipeline only (`EXECUTION_MODE=pipeline`) |

### `sen login`

```bash
# 1. Generate the credential blob — Base64 of client_id:secret, no "Basic" prefix:
printf '%s:%s' "<client_id>" "<client_secret>" | base64          # Linux/macOS
```
```powershell
[Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("<client_id>:<secret>"))   # Windows
```

```bash
# 2. Copy src/apiops_orchestrator/.sen.example to src/apiops_orchestrator/.sen
#    and fill in SEN_CREDENTIALS, AUTH_HOST and AUTH_LOGIN_PATH.
# 3. Run:
poetry run sen login
```

The session is written to `.sen_session` in the **package directory** (`src/apiops_orchestrator/`, next to `.sen`; in the frozen executable, next to the binary). It is hidden, owner-only and git-ignored.

> **Nota (console script `sen`):** o binário `sen` é criado a partir de
> `[tool.poetry.scripts]` no `pyproject.toml` quando o próprio pacote é
> instalado no ambiente — via Poetry (`poetry install`) **ou** via pip
> (`pip install -e .`, já contemplado no setup da Opção A).
> O `sen --version` degrada graciosamente para uma versão estática caso a
> metadata do pacote não esteja disponível. Em ambos os ambientes, a
> alternativa `python src/apiops_orchestrator/main.py sen <comando>`
> (ou `poetry run python ...`) continua funcionando e aceita os mesmos comandos.

## Configuration

### Where values come from

Precedence, highest first:

1. **Process environment** (shell `export`, pipeline vault)
2. **`.sen`** in the package directory (`src/apiops_orchestrator/.sen`) — template: `.sen.example`
3. **`.env`** in the project root — template: `.env.example`

The two files are gap-filled into the environment (never overriding what is already set), so a value exported in the shell always wins. Any of the three sources can provide any key.

> **Quotes:** `VAR="value"` is unwrapped by dotenv when it comes from `.sen`/`.env`, but exported directly in the environment the quotes stay **inside** the value. `Settings` strips a symmetric pair of quotes (single or double) from `HOST`, `AUTH_HOST`, `AUTH_LOGIN_PATH`, `AUTH_VALIDATE_PATH` and `SEN_CREDENTIALS`, so both forms work. A lone quote on one side is kept — that is data, not wrapping.

### Variables

| Variable | Required | Purpose |
|---|---|---|
| `SEN_CREDENTIALS` | for `sen login` | Base64 of `client_id:secret`, no `Basic` prefix |
| `AUTH_HOST` | yes | Host of the Orchestrator Auth API |
| `AUTH_LOGIN_PATH` | yes | Token path; concatenated to `AUTH_HOST` |
| `AUTH_VALIDATE_PATH` | no | Session validation path. Default: `{AUTH_LOGIN_PATH}/validation` |
| `HOST` | no — keep the default | **Sensedia Manager** targeted by `list`, `completeness`, `validate`, `publish`, `deploy` |
| `EXECUTION_MODE` | no | `local` (default) or `pipeline` |
| `TEMPLATE_API_ID` | pipeline only | Golden Path API id; inject from the vault |
| `TARGET_REVISION_NUMBER` | pipeline only | Revision **number** as shown in the UI (1=Draft, 2=DEV, 3=HML, 4=PRD) |
| `TARGET_ENVIRONMENT_ID` | pipeline only | Manager id of the environment receiving `sen deploy` |

> **`HOST` and `AUTH_HOST` are separate on purpose.** The Manager is always `https://platform-production.sensedia.com` — that is the default in the code and the expected target, so normally you leave `HOST` unset. `AUTH_HOST` is configured per environment because the Orchestrator Auth API is published separately from the Manager; authenticating against one does not change which Manager the commands reach, and it is not supposed to. Set `HOST` only to point at a different Manager.
>
> To see which Manager answered — useful when confirming a new environment or credential:
> ```bash
> sen list api --limit 5
> ```

See `.env.example` and `src/apiops_orchestrator/.sen.example` for annotated templates.

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

### 2. Configure the credentials

Follow [Configuration](#configuration): copy `src/apiops_orchestrator/.sen.example` to `.sen` and fill in `SEN_CREDENTIALS`, `AUTH_HOST` and `AUTH_LOGIN_PATH`. Set `HOST` if the Manager is not the default one.

### 3. Run

```bash
poetry run sen login
poetry run sen list api --limit 10
```

With the pip environment, use the local interpreter:
```powershell
.\.venv\Scripts\sen.exe login
```

`sen --help` and `sen --version` answer without any `.env`/`.sen`: configuration is only loaded by the command that actually needs it.

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
- `src/apiops_orchestrator/main.py` — CLI entry point and lazy Composition Root.
- `src/apiops_orchestrator/config/settings.py` — Configuration and environment variables.
- `src/apiops_orchestrator/adapters/*` — Inbound (CLI) and outbound (HTTP, files) adapters.
- `src/apiops_orchestrator/application/*` — Application use cases and services.
- `src/apiops_orchestrator/domain/*` — Domain models, ports, and services.
- `src/apiops_orchestrator/infrastructure/*` — Infrastructure integrations (HTTP client, session storage, logging).
- `tests/unit/...` — Unit tests.

## Tech Stack
- Python 3.12+
- Typer + Rich (CLI)
- Pydantic Settings (environment configuration)
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
