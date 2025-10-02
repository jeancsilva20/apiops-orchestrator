**Nome Do Projeto**
- apiops-orchestrator

**Descrição Geral**
- Orquestrador APIOps em Python para compor, validar, planejar e aplicar mudanças de APIs no Sensedia Manager a partir de artefatos (ex.: OpenAPI). Interface principal via CLI construída com Typer. Estrutura do código segue princípios de Arquitetura Hexagonal (adapters, application, domain, infrastructure).
- Estado atual: funcionalidades em desenvolvimento; CLI e configuração inicial implementadas.

**Funcionalidades Principais**
- CLI APIOps com Typer: `src/apiops_orchestrator/adapters/inbound/cli/cli_adapter.py`.
- Comando `sync-openapi` (em construção):
  - Opções obrigatórias: `--repo/-r` (caminho do repositório da API), `--env/-e` (ambiente alvo, ex.: `dev`, `hmg`, `prd`).
  - Opções opcionais: `--apply/--no-apply` (aplica alterações via POST /revisions; padrão DRY-RUN), `--out-dir` (diretório para salvar o plano).
  - Comportamento atual: imprime os parâmetros recebidos e finaliza; a lógica de diff/planejamento/aplicação será adicionada nas próximas iterações.
- Comando `placeholder`: reservado para manter a raiz do Typer e para futura extensão da CLI.
- Configurações via variáveis de ambiente com `.env` suportado: `src/apiops_orchestrator/config/settings.py`.
  - `APIOPS_APIS_REPO_ARTIFACTS_PATH` (padrão: `src/artifacts`).
  - `APIOPS_APIS_REPO_REVISIONS_PATH` (padrão: `src/apis/revisions`).
- Testes de unidade iniciais para a CLI: validação do `--help` e de opções obrigatórias em `tests/unit/adapters/inbound/cli/test_cli_adapter.py`.

**Como Rodar O Projeto**
- Pré‑requisitos: Python 3.10+.
- Crie e ative um ambiente virtual:
  - Windows: `python -m venv .venv && .venv\Scripts\activate`
  - Linux/macOS: `python -m venv .venv && source .venv/bin/activate`
- Instale dependências básicas de desenvolvimento: `pip install typer rich pydantic-settings pytest`
- (Opcional) Configure um arquivo `.env` na raiz com as chaves acima.
- Execute a CLI (ajuste os caminhos conforme seu SO):
  - Ajuda geral: `python src/apiops_orchestrator/main.py --help`
  - Ajuda do comando: `python src/apiops_orchestrator/main.py sync-openapi --help`
  - Exemplo de uso: `python src/apiops_orchestrator/main.py sync-openapi -r C:\caminho\da\api -e dev --no-apply --out-dir C:\temp\plano`
- Rode os testes: `pytest -q`

**Tecnologias Utilizadas**
- Python 3.10+
- Typer (CLI)
- Rich (saída colorida)
- Pydantic Settings (configuração por ambiente/.env)
- Pytest (testes)

**Estrutura De Pastas**
- `src/apiops_orchestrator/main.py` — ponto de entrada da CLI.
- `src/apiops_orchestrator/adapters/inbound/cli/cli_adapter.py` — comandos Typer (`sync-openapi`, `placeholder`).
- `src/apiops_orchestrator/config/settings.py` — configurações e variáveis de ambiente.
- `src/apiops_orchestrator/adapters/*` — camadas de adaptação (inbound/outbound, esqueleto).
- `src/apiops_orchestrator/application/*` — casos de uso (esqueleto).
- `src/apiops_orchestrator/domain/*` — modelos, portas e serviços (esqueleto).
- `src/apiops_orchestrator/infrastructure/*` — integrações infra (esqueleto).
- `tests/unit/...` — testes da CLI.

**Contribuidores**
- Augusto
- Danilo Amaral
- Matheus Alves Giroto

**Status Do Projeto**
- Em desenvolvimento.

