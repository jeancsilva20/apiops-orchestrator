# Backlog — Distribuição da CLI e origem das credenciais

> **Status:** proposta registrada, aguardando spec própria (OpenSpec change futura).
> **Origem:** discussão de 16/09/2026 durante o apply de `add-sen-login` — ficou acordado **finalizar a
> fase atual como está** e especificar este ajuste separadamente, com calma.
> **Relacionados:** ADR 0001/0002/0004/0005 · `openspec/changes/add-sen-login` (fase 1 concluída)

## 1. Objetivo

Definir, por ambiente, **de onde vêm as credenciais da CLI** (`SEN_CREDENTIALS`, `AUTH_HOST`,
`AUTH_LOGIN_PATH`) e como a ferramenta é **entregue/distribuída**, sem depender de "rodar da raiz do repo".

## 2. Situação atual (fase 1 — congelada)

- `Settings` (pydantic-settings) lê: **env vars do processo > `.env` localizado via `PROJECT_ROOT`**
  (`PROJECT_ROOT = Path(__file__).parent…parent` → raiz do repo).
- Comportamento correto nos cenários testados (repo clonado + esteira com `.env` gerado), mas **não** para
  artefato instalado (`pip install` wheel): o `PROJECT_ROOT` apontaria para `site-packages`.

## 3. Matriz-alvo (proposta)

| Ambiente | Origem da credencial | Pasta/arquivo | Observação |
|---|---|---|---|
| **Esteira (CI/CD)** | Secrets (GitHub/Bitbucket) → **env vars do processo** | **nenhuma** (nada persistido — ADR 0002) | aposentar o `printf "> .env"` do `bitbucket-pipelines.yml` |
| **Dev com repo (poetry)** | `.env` na **raiz do projeto** | raiz do clone | comportamento atual mantido |
| **Dev com wheel (pip)** | `.env` do **CWD** (onde roda `sen`) → fallback `~/.sen/.env` | pasta de uso | **nunca** dentro de `src/`/site-packages (secrets não podem ser empacotadas no artefato) |

## 4. Ajustes a especificar (inputs para a próxima spec)

1. **Lookup de configuração**: migrar resolução de `.env`/`PROJECT_ROOT` para ordem
   `CWD → $HOME/.sen → (repo, quando executado do clone)` — 5–10 linhas em `config/settings.py`,
   com teste para cada caminho.
2. **Esteira**: registrar `SEN_CREDENTIALS`/`AUTH_HOST`/`AUTH_LOGIN_PATH` como Secrets; remover geração
   de `.env` do pipeline (validar que `python main.py` bare lê env vars direto).
3. **Entrypoint `sen`**: adicionar `[tool.poetry.scripts] sen = "apiops_orchestrator.main:main"`
   ao `pyproject.toml` (requisito para os cenários wheel/instalado; discutido e postergado em 16/09/2026).
   Lembrar: `sen` pelado = modo bare (paridade com `python main.py`) — comunicar à equipe.
4. **Empacotamento** (decidir junto): wheel publicado no index interno? PyInstaller? Define se a fase
   inclui `tbump`/CI de release.
5. **Privacidade**: garantir que nada do `.env` da máquina do dev vaza no wheel (revisar `.dockerignore`
   e build step).

## 5. Pré-requisitos para abrir a spec

- Fechar a fase 1 (`add-sen-login`) — arquivar a change quando o time aprovar.
- Definir com o time (Isaac/Jean): senha da esteira **já migrada** para `SEN_CREDENTIALS`?
  (depende do backlog 0002/0004 — migração GitHub Secrets → Base64).
- Resolver divergência D1 aberta (`docs/auth/divergencias-abertas.md`) quanto à custódia na esteira.

## 6. Decisão registrada

- "Vamos finalizar como está agora e depois especificamos esse ajuste em específico."
- Aviso do orchestrator: credenciais nunca em `src/` (empacotadas) — fonte canônica =
  env vars (esteira) ou `.env` de CWD (dev).
