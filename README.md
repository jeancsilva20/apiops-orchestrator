# apiops-orchestrator

Orquestrador APIOps em Python para compor, validar, planejar e aplicar mudanças de APIs no Sensedia Manager a partir de artefatos (ex.: OpenAPI). A interface principal é uma CLI construída com Typer. O código segue princípios de Arquitetura Hexagonal (adapters, application, domain, infrastructure).

> Status: em desenvolvimento

## Sumário
- Visão Geral
- Funcionalidades
- Como Rodar
- Estrutura de Pastas
- Tecnologias
- Contribuidores

## Visão Geral
- CLI em `src/apiops_orchestrator/main.py` e comandos definidos em `src/apiops_orchestrator/adapters/inbound/cli/cli_adapter.py`.
- Configuração por variáveis de ambiente (suporta `.env`) em `src/apiops_orchestrator/config/settings.py`.
- Testes de unidade iniciais: `tests/unit/adapters/inbound/cli/test_cli_adapter.py`.

## Funcionalidades
- Comando `sync-openapi` (em construção):
  - Obrigatórias: `--repo/-r` (caminho do repositório da API), `--env/-e` (ambiente: `dev`, `hmg`, `prd`).
  - Opcionais: `--apply/--no-apply` (aplica mudanças via POST /revisions; padrão DRY-RUN), `--out-dir` (diretório para salvar o plano).
  - Comportamento atual: imprime os parâmetros recebidos e finaliza. A lógica de diff/planejamento/aplicação será adicionada nas próximas iterações.
- Comando `placeholder`: reservado para manter a raiz do Typer e futuras extensões da CLI.

Variáveis de ambiente suportadas:

| Variável | Descrição | Padrão |
| --- | --- | --- |
| `APIOPS_APIS_REPO_ARTIFACTS_PATH` | Caminho base dos artefatos das APIs | `src/artifacts` |
| `APIOPS_APIS_REPO_REVISIONS_PATH` | Caminho para revisões das APIs | `src/apis/revisions` |

## Como Rodar

Pré‑requisitos: Python 3.10+

Crie e ative um ambiente virtual:

Windows
```powershell
python -m venv .venv
.venv\Scripts\Activate
```

Linux/macOS
```bash
python -m venv .venv
source .venv/bin/activate
```

Instale dependências de desenvolvimento:
```bash
poetry install
```

Opcional: crie um `.env` na raiz com as variáveis acima.

Ajuda e exemplos de uso:
```bash
# ajuda geral da CLI
python src/apiops_orchestrator/main.py --help

# ajuda do comando
python src/apiops_orchestrator/main.py sync-openapi --help

# exemplo
python src/apiops_orchestrator/main.py sync-openapi \
  -r C:\\caminho\\da\\api -e dev --no-apply --out-dir C:\\temp\\plano
```

Rodar testes:
```bash
pytest -q
```

## Estrutura de Pastas
- `src/apiops_orchestrator/main.py` — ponto de entrada da CLI.
- `src/apiops_orchestrator/adapters/inbound/cli/cli_adapter.py` — comandos Typer (`sync-openapi`, `placeholder`).
- `src/apiops_orchestrator/config/settings.py` — configurações e variáveis de ambiente.
- `src/apiops_orchestrator/adapters/*` — camadas de adaptação (inbound/outbound, esqueleto).
- `src/apiops_orchestrator/application/*` — casos de uso (esqueleto).
- `src/apiops_orchestrator/domain/*` — modelos, portas e serviços (esqueleto).
- `src/apiops_orchestrator/infrastructure/*` — integrações de infraestrutura (esqueleto).
- `tests/unit/...` — testes da CLI.

## Tecnologias
- Python 3.10+
- Typer (CLI)
- Rich (saída colorida)
- Pydantic Settings (configuração por ambiente/.env)
- Pytest (testes)

## Contribuidores
- Augusto
- Danilo Amaral
- Matheus Alves Giroto

---
Consulte também `CHANGELOG.md` para o histórico de mudanças.

