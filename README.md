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
| `sen list api` | Lists APIs in the Manager | `--id`, `--query`, `--limit`, `--offset`, `--all`, `--revisions/-r`, `--owner`, `--team`, `--context`, `--workflow`, `--stage`, `--wide/-w` |
| `sen completeness` | Completeness of an API revision | `--id`, `--revision`, `--score-only` |
| `sen validate` | Validates the repository and writes to Draft | `--repo` (default: current directory) |
| `sen publish` | Publishes to the environment revision | Pipeline only (`EXECUTION_MODE=pipeline`) |
| `sen deploy` | Deploys the revision to the environment | Pipeline only (`EXECUTION_MODE=pipeline`) |
| `sen get api` | Identity, visibility, environments and revisions of one API | `--id` |
| `sen get resources` | Root → resources → operations of a revision, with destination and interceptor counts | `--id`, `--revision`, `--revision-id` |
| `sen get interceptors` | Interceptor flow per scope; `--item` zooms into one interceptor | `--resource`, `--operation`, `--effective`, `--content`, `--item` |
| `sen get custom` | Name and script of a Custom interceptor from the catalog | `--custom-id`, `--script-only` |
| `sen get swagger` | OpenAPI contract of a revision, as stored in the Manager | `--id`, `--revision`, `--revision-id` |
| `sen export api` | Materializes the canonical repository tree of a revision | `--dir`, `--force` |
| `sen list environments` | Environments of the tenant (ids, names, inbound URLs) | |
| `sen list workflows` | Adaptive Governance workflows and their stages | |
| `sen list attributes` | Governance attributes (the `apiTags` names) and their valid tags | |
| `sen list interceptors` | Catalog of interceptor types (the `type` accepted in YAML) and custom ids | `--custom`, `--tag` |
| `sen get workflow` | Stages of a workflow and what each one requires | `--id` |
| `sen get governance` | A revision against its current stage and the next one: maturity, mandatory interceptors, attributes, environments | `--id`, `--revision`, `--revision-id` |
| `sen get impact` | Impact graph: routes with destinations, plans and apps consuming the API | `--id`, `--env` |
| `sen list variables` / `sen get environment` | Environment variables by map (always masked) and everything deployed in an environment | `--env`, `--key` |
| `sen reveal variable` | Unmasks one environment variable on purpose | `--env`, `--key`, `--map`, `--raw` |
| `sen list apps` / `sen get app` | Consumer apps and their API → plan subscriptions (no credentials) | `--api`, `--query` |
| `sen list plans` / `sen get plan` | Plans, their API and the interceptors a plan adds | `--api`, `--query` |
| `sen list tokens` | Issued access tokens (owner, app, status, expiry; never the code) | `--app`, `--api` |
| `sen list users` / `sen list teams` | Access Control users and teams | `--query` |
| `sen get user` / `sen get team` / `sen list roles` / `sen get role` / `sen list permissions` | Access Control in depth: a user's teams and roles, a team's members, roles and their permissions | `--username`, `--name`, `--id`, `--product` |
| `sen list owners` | APIs grouped by owner, with context and teams | |
| `sen get interceptor-type` | Reference of each interceptor type's `content` fields (doc 06 + tenant) | `--type` |
| `sen list inbounds` / `sen list gateway-pools` | Gateway inbound addresses and pools | |

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

### Exploring an environment without the source (`sen get`, `sen export`)

> The complete, per-command reference (every option, what each level shows, what is masked and what is not reachable) is in [COMMANDS.md](COMMANDS.md). The coverage plan by area (API data, owners, access control, governance, apps, plans, environments, interceptors in FIRST/SECOND/THIRD, interceptor content), with what was validated against the APIM/AG mapping and what is out of reach, is in [PLANO-NAVEGACAO.md](PLANO-NAVEGACAO.md).

The `get` and `export` groups read an API straight from the Manager, so a person — or a coding agent such as Claude Code that only has the CLI — can inspect APIs **without a local copy of the repository**. Every command is read-only, accepts `-o json`/`-o yaml`, and each level of detail points to the next:

```bash
sen list api                                            # 0. which APIs exist (ids)
sen get api --id 400                                    # 1. identity, visibility, environments, revisions
sen get resources --id 400 --revision 4                 # 2. root → resources → operations, counts per scope
sen get interceptors --id 400 --revision 4              # 3. interceptors each scope declares (own)
sen get interceptors --id 400 --resource Token --effective   #    what a scope actually runs (inherited − removed + own)
sen get interceptors --id 400 --operation "POST /oauth2/token" --content   #    with each interceptor's configuration
sen get interceptors --id 400 --item 19220              # 4. one interceptor, full content (script included)
sen get custom --custom-id 31 --script-only > my.js     #    script of a Custom from the catalog
sen get swagger --id 400 --revision 4                   #    OpenAPI contract of the revision
sen export api --id 400 --revision 4 --dir ./repo       # 5. canonical tree (what `sen validate` reads)
```

The catalogs and the governance view come from the routes mapped in the APIM/Adaptive Governance documentation (`/environments`, `/api-governance/.../workflows`, `/attributes`, `/interceptors`, `/apis/{id}/tree-analysis/{env}`):

```bash
sen list environments                                   # env ids for TARGET_ENVIRONMENT_ID and for stage rules
sen list workflows                                      # workflows → stages, with a one-line summary of each stage's rules
sen get workflow --id 327                               # what each stage requires (maturity, interceptors, attributes, deploy envs)
sen list attributes                                     # apiTags names and the tags the catalog accepts
sen list interceptors [--custom] [--tag Oauth]          # valid `type` names; custom ids for `sen get custom`
sen get governance --id 400 --revision 4                # does the revision meet its stage? what is missing for the next one?
sen get impact --id 400 [--env 1]                       # routes → destinations, plans → apps (who breaks if this API changes)
```

Notes:

- `sen get governance` evaluates the stage requirements against the revision as the Manager holds it: maturity against `/completeness`, mandatory interceptors against the effective flow of each scope (root, every resource or every operation, honouring `positionType` FIRST/LAST), attributes against `apiTags` with the same rule the publish pre-check uses, and deployments against the stage's allowed environments. Attribute bindings made in the UI side panel travel on a signed route the CLI cannot read, so only `apiTags` count.
- `--revision` is the revision **number** shown in the UI (REV #). Use `--revision-id` for the Manager id (REV ID, the value `sen completeness --revision` expects). Without either, the current revision (`lastRevision`) is used.
- `--resource` accepts the resource name, its slug (the folder name in the canonical tree) or its id; `--operation` accepts `"<METHOD> <path>"`, just the path, or the operation id.
- Interceptor ids (`[19220]`) are the Manager ids inside the revision; `customInterceptorId` is the catalog id used by `sen get custom`.
- `sen export api` without `--dir` prints every file to stdout, with a `# ==> <path>` header per file; with `--dir` it writes the tree and refuses to overwrite unless `--force` is given.
- Only `FIRST`/`SECOND` execution points are governed by the repository; interceptors outside them are counted as *preserved* and never appear in the exported YAML.

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
