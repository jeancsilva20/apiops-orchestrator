# Padrões de Desenvolvimento — apiops-orchestrator

Documento consolidado de padrões do projeto, extraído da varredura do código, testes, configurações e
decisões registradas (ADRs). Serve como guia para novos módulos/features manterem consistência.

> Origem: análise dos arquivos de `src/`, `tests/`, `docs/`, `openspec/` e configs raiz.
> Documentação canônica do programa vive em `Plataforma-Sensedia/API Ops - docs/Docs revisados/` (ver `docs/README.md`).

---

## 1. Stack e ferramentas

| Ferramenta | Uso | Referência |
|---|---|---|
| **Python 3.12** (`^3.12` no Poetry; imagem `python:3.12` no CI e Dockerfile) | Runtime | `pyproject.toml` |
| **Poetry** | Dependências e build (`poetry install`, grupos `[tool.poetry.group.dev.dependencies]`) | `pyproject.toml` |
| **Typer + Rich** | CLI e saída formatada (`rprint`, tabelas/markup) | `adapters/inbound/cli/` |
| **Pydantic v2 + pydantic-settings** | Models de domínio e configuração por ambiente | `config/settings.py` |
| **python-dotenv** | Carregamento do `.env` da raiz do projeto | `config/settings.py` |
| **PyYAML + jsonschema** | Leitura de artefatos YAML e validação por schema | `application/services/` |
| **requests** | Cliente HTTP compartilhado | `infrastructure/utils/http_client.py` |
| **pytest + pytest-cov** | Testes (`pytest.ini`: `pythonpath = src`) | `tests/` |
| **Qualidade**: black, ruff, mypy, flynt, deptry, bandit, safety, pre-commit, tox | Toolchain dev (instaladas via Poetry) | `pyproject.toml` |

Executar sempre via Poetry: `poetry run python src/apiops_orchestrator/main.py ...` e `poetry run pytest`.

## 2. Arquitetura hexagonal e organização de pastas

O código segue Arquitetura Hexagonal (adapters, application, domain, infrastructure):

```
src/apiops_orchestrator/
├── main.py                  # Composition Root (instancia adapters/services e injeta na CLI)
├── config/
│   └── settings.py          # Settings (pydantic-settings), paths do projeto, regras de layout
├── adapters/
│   ├── inbound/             # Entradas do sistema (CLI, importador de arquivos locais)
│   │   ├── cli/             # cli_adapter.py, output_format.py, output_display.py
│   │   └── local_files_importer/
│   └── outbound/            # Saídas/integrações (HTTP, exporters, template repo, diff engine)
│       ├── http/common/     # http_error_mapper.py (RFC 7807)
│       └── http/<api_name>/ # Um pacote por API externa (manager_api, orchestrator_auth_api, user_management_api)
├── application/
│   ├── services/            # Casos de uso (LoginService, ConversorService, ...)
│   ├── exceptions/          # Hierarquia de erros de aplicação
│   └── enums/
├── domain/
│   ├── models/              # Models Pydantic
│   ├── ports/               # Interfaces ABC (contratos outbound)
│   ├── services/            # Serviços de domínio puros
│   └── schemas/             # JSON Schemas dos artefatos (+ catalog.json)
└── infrastructure/
    ├── observability/       # logging.py, enums Level/Status
    ├── secure_storage/      # session_store.py (arquivo oculto, escrita atômica)
    └── utils/               # http_client.py, critical_exception_handler.py
```

Regras estruturais:

- **Um pacote por API externa** em `adapters/outbound/http/` (nome em `snake_case`: `manager_api`, `orchestrator_auth_api`), contendo um adapter.
- **Ports (ABC)** em `domain/ports/` definem contratos; **adapters implementam ports**; services recebem ports/adapters via construtor (nunca instanciam integrações internamente).
- **Composition Root centralizado em `main.py`**: padronizou-se o padrão **factory** (`build_login_service_factory`, `build_listing_service_factory`) montando grafos de dependência; a CLI recebe esses objetos via `ctx.obj` do Typer.
- Pastas ainda não utilizadas permanecem no scaffold com `.keep` (ex.: `diff_engine`, `template_repo`) — mantenha esse convênio ao criar novas áreas planejadas.

## 3. Convenções de nomenclatura

| Elemento | Padrão | Exemplo |
|---|---|---|
| Arquivo de modelo | `*_model.py` | `login_session_model.py`, `api_partial_model.py` |
| Port | `*_port.py` / classe `XxxPort` | `orchestrator_auth_port.py`, `OrchestratorAuthPort` |
| Adapter | `xxx_adapter.py` / classe `XxxAdapter` | `orchestrator_auth_adapter.py`, `OrchestratorAuthAdapter` |
| Service (caso de uso) | `*_service.py` / classe `XxxService` | `login_service.py`, `LoginService` |
| Exceções agrupadas | `<modulo>_exceptions.py`, classe base `XxxError` | `login_exceptions.py`, `LoginError` |
| Enums | `*_enum.py`, classes herdam `(str, Enum)` | `OutputFormat`, `Level`, `Status` |
| Constantes de módulo | `UPPER_SNAKE_CASE` | `REQUIRED_SESSION_FIELDS`, `SESSION_FILE_NAME`, `PROJECT_ROOT` |
| Métodos "privados" internos | `_underscore` + nome claro | `_resolve_inputs`, `_perform_login`, `_get_headers` |
| Factories no composition root | `build_<fluxo>_factory(settings)` | `build_login_service_factory` |
| Classes e funções | `PascalCase` / `snake_case` (PEP 8, sem prefixos); imports sempre absolutos | `from apiops_orchestrator.application.services.login_service import LoginService` |
| Docstrings | **Em inglês**, explicando o "porquê"; aceita docstrings para modules/classes/métodos públicos | `"""Single credential source: SEN_CREDENTIALS ..."""` |
| Mensagens de usuário (CLI/exceções) | **PT-BR** | `"Login realizado com sucesso."` |

Observação sobre língua: comentários/docstrings estão majoritariamente em inglês; mensagens voltadas ao usuário final ficam em português. Siga essa separação em novos módulos.

## 4. Variáveis de ambiente e configuração ⭐

Padrão dominante do projeto — tratado como contrato (ADRs 0004/0006, testes dedicados).

### 4.1 Nomenclatura

- Todas em **`UPPER_SNAKE_CASE`**, no arquivo **`.env` da raiz do projeto** (perfil atual — ver perfis em §4.3; documentado por `.env.example`, que é o gabarito versionado; o `.env` real é git-ignored).
- Prefixo por **domínio** indica grupo/produto:

| Prefixo | Domínio | Exemplos |
|---|---|---|
| *(nenhum)* | Configuração base da plataforma | `HOST`, `REQUEST_TIMEOUT`, `KIND_VERSION` |
| `OAUTH_` | Credenciais OAuth legadas (transicionais — ver ADR 0004) | `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET` |
| `AUTH_` | API de autenticação da CLI | `AUTH_HOST`, `AUTH_LOGIN_PATH`, (planejada: `AUTH_VALIDATE_ACTION_PATH` — ADR 0003) |
| `SEN_` | Credencial canônica da CLI (blob `Base64(client_id:secret)`) | `SEN_CREDENTIALS` |
| `API_TAGS_<DESCRICAO>` | Colete dinâmico de tags: formato `AttributeName:tag1,tag2` | `API_TAGS_CUSTOMER=Customer:internal,external` |
| `LOG_` | Observabilidade | `LOG_LEVEL` (`INFO` default), `LOG_FORMAT` (`SIMPLE|FILE|BOTH`) |
| `WORKFLOW_` | Adaptive Governance | `WORKFLOW_ID`, `WORKFLOW_STAGE_ID` |

- Novas variáveis devem seguir: nome pode se remeter à entidade (não genericamente "TOKEN"/"KEY"), sem "herdar" semântica de headers HTTP (motivo da rejeição de `AUTHORIZATION` no ADR 0004).

### 4.2 Cadastro obrigatório em 3 lugares (4 quando exigida)

1. **`config/settings.py`** — declarar no `Settings` com tipagem Pydantic:

   ```python
   AUTH_HOST: str                      # obrigatória (sem default)
   SEN_CREDENTIALS: str | None = None  # opcional no Settings (falha depois, no service, com erro categorizado)
   ```

   - Obrigatórias ficam **sem default** (Pydantic falha rápido com mensagem lista as `loc` em maiúsculas).
   - Opcional com sentinela `None` + checagem no ponto de uso (`resolve_credential`), para dar erro **categorizado e amigável** em vez de falha de carga de settings.
2. **`.env.example`** — adicionar entrada com comentário explicando formato/geração e exemplo do comando de geração (variáveis de plataforma/esteira). **Exceção (ADR 0007):** as chaves de autenticação do executável (`SEN_CREDENTIALS`, `AUTH_HOST`, `AUTH_LOGIN_PATH`) têm gabarito próprio — **`src/apiops_orchestrator/.sen.example`** (o `.env.example` não as documenta mais).
3. **Teste de contrato** — estender `tests/unit/config/test_settings_login_vars.py`: lista `REQUIRED_VARS`, isolamento de fontes via fixture `autouse` (`monkeypatch.setattr(Settings, "model_config", ...)`) e seed via `monkeypatch.setenv`.
4. Quanto afetar comportamento visível: atualizar `docs/features/*.md` e/ou novo ADR.

### 4.3 Perfis de execução (pensar sempre nos dois casos)

Hoje tudo roda na máquina do dev (Poetry + `.env` na raiz), mas código novo deve ser construído para **duas formas de rodar**:

| Perfil | Como funciona | Configuração |
|---|---|---|
| **Esteira** | CI invoca os comandos da CLI e encerra a execução ao final (processo efêmero, não interativo) | Variáveis de ambiente injetadas pela esteira (hoje, secrets geram um `.env` em runtime) |
| **Executável para devs** | Binário distribuído com o conteúdo do apiops-orchestrator | Arquivo `.sen` **colado ao executável/artefato** recebido pelo dev |

Implicações práticas:

- **Nunca assumir `.env` da raiz**: fontes de credencial/config devem ficar atrás de pontos únicos de resolução (ex.: `resolve_credential`) para trocar a fonte sem tocar nos casos de uso.
- **Caminhos**: `PROJECT_ROOT` deriva de `Path(__file__)`, o que não vale em executável congelado — no modo distribuído, caminhos de arquivos/assets devem considerar o **diretório do binário**.
- **Headless na esteira**: sem interação; todo comando encerra com código de saída do contrato (§5).
- Evolução anunciada: **implementada em 17/09/2026 (ADR 0007)** — o bloco de credenciais de login (`SEN_CREDENTIALS`, `AUTH_HOST`, `AUTH_LOGIN_PATH`) mora no arquivo **`.sen`** do `PACKAGE_ROOT` (gabarito `.sen.example` versionado junto), com precedência **processo > `.sen` > `.env`**; o `.env` tende a deixar de existir (acompanhar §14).

### 4.4 Paths derivados de configuração

Paths de layout do repositório externo ficam como atributos no `Settings` (não hardcoded espalhado):

```python
PROJECT_ROOT: Path = PROJECT_ROOT           # resolvido via Path(__file__) em tempo de import
API_REPO_FOLDER: Path = "./external-repo"
API_REPO_API_INFO_FOLDER: str = "api-info"  # novo layout: api-info / environments / revisions
ORCHEST_SCHEMA_FOLDER: str = "apiops_orchestrator/domain/schemas"
NEW_STRUCTURE_VALIDATION_RULES: dict = {...}
```

Exceção técnica atual: `repo_path` em `main.py` ainda é hardcoded/absoluto (devedor reconhecido no README) — **não reproduzir** em código novo; preferir `Settings` ou parâmetro de comando.

## 5. Erros e códigos de saída

- Hierarquia por módulo em `application/exceptions/`:

  ```python
  class LoginError(Exception):
      exit_code = 1
      def __init__(self, message: str, exit_code: int | None = None): ...
  ```

- Subclasses **categorizam** o modo de falha com `exit_code` estável (ex.: `CredentialNotFoundError`=2, `AuthenticationRejectedError`=3, `LoginProtocolError`=4, `SessionPersistenceError`=5). Erros puramente de infraestrutura nem sempre entram na hierarquia (ex.: `SessionStorageError` em `session_store.py`) e são traduzidos pela camada de aplicação em erro categorizado (`raise XxxError(...) from exc`).
- Mensagem de exceção: texto PT-BR **orientando a ação do usuário** ("configure a variável … e rode `sen login` novamente"), nunca conteúdo de segredos/sessão.
- Na borda da CLI: capturar erro do módulo → `rprint("[bold red]...[/bold red]")` → `raise typer.Exit(code=e.exit_code)`; `CliError(message, exit_code)` cobre erros genéricos de CLI; `main.py` também trata `pydantic.ValidationError` (lista vars faltantes em caixa alta) e sai com `1`.

## 6. Logging e observabilidade

Infraestrutura própria em `infrastructure/observability/` — **reutilize, não reinvente** (ADR 0005):

- `setup_logging()` é chamada **somente no entrypoint**; níveis/formatos por variável `LOG_LEVEL` e `LOG_FORMAT`.
- Console humano (`SimpleFormatter`, cores ANSI) + arquivo NDJSON (`JsonFormatter`) em `logs/.<timestamp>.ndjson`.
- Formato JSON: `timestamp (UTC, ISO 8601 com Z)`, `trace_id`, `level`, `service`, `message`, `duration` (ms), `status` (`IN PROGRESS|SUCCESS|FAILURE`) e `context{api_id, customer, span_id}`.
- Contexto **thread-local** com helpers oficiais: `set_default_data()`, `set_span_id()`, `set_status()`, `set_api_info()`, `clear_operation_context()`, `clear_context()` — sempre limpar no fim da operação.
- Medição de duração: `with log_duration("nome.operacao"):`.

Convenções de mensagem (chaves estáveis, estilo `domain.event`/`domain.event.details`):

```
logger.info("auth.login.started")
logger.info("auth.login.failure category=%s", type(exc).__name__)
logger.info("auth.session.expired")
```

- Logger de módulo: `logger = logging.getLogger(__name__)`.
- Logs vão como **texto estruturado/dados**, nunca via `print`/`rprint` (rich é reservado à UX da CLI); nunca logar headers de authorization, tokens, Base64 ou segredos — inclusive `--verbose`.

## 7. Chamadas HTTP (cliente compartilhado)

- **Todo acesso HTTP passa por `HttpClient.request()`** (`infrastructure/utils/http_client.py`), que encapsula:
  - retry em 5xx (`max_retries`, default 3; espera `interval`, default 5s);
  - timeout default 30s (`REQUEST_TIMEOUT` no settings base);
  - log e status de observabilidade (`set_span_id`, `log_duration`, `set_status`);
  - mapeamento de erros 4xx para corpo **RFC 7807** (`HttpErrorMapper`), impresso em `stderr` por `Console(stderr=True)` — pode ser suprimido por quem possui próprio UX de erro (`report_client_errors=False`, adotado pelo fluxo `sen login`).
- Adapters HTTP não fazem `requests` direto; eles compõem `url = host + base_path + endpoint`, montam headers num helper `_get_headers()` (`Authorization: Bearer ...`) e delegam ao `HttpClient`.
- Método recebido sempre em caixa-alta (`"GET"`, `"POST"`); respostas consumidas como `dict` (`response.json()`), com fallback para texto/`{}`.
- Clientes da CLI para HTTP devem propagar erro via `typer.Exit` (4xx) ou exceção — nunca engolir.

## 8. CLI (Typer + Rich)

- Apps compostos: um `typer.Typer` raiz (`main_app`), sub-apps nomeados (`sen_app` com `name="sen"`), agrupamentos de comandos em sub-typers (`list_app`). Flags comuns: `no_args_is_help=True`, `add_completion=False`.
- Opções: `typer.Option(default, "--flag", "-f", help="...")`; sintaxe **--kebab-case**; valores tipados e enums (`OutputFormat` `text|json|yaml`) para saída.
- Saída: **`rprint` com markup Rich** (`[bold green]...[/bold green]`, `[bold red]Error:[/bold red]`); nada de `print` cru. Erros de HTTP vão para `stderr` (ver §7).
- Serviços chegam aos comandos por `ctx.obj` (dict de factories/serviços construídos no composition root) — comandos **não instanciam** adapters, apenas consomem factories do contexto; ausência esperada do contexto gera mensagem clara + `Exit(1)`.
- Flag `--verbose/-v` controla apenas **verbosidade**, nunca formato (convenção canônica citada no ADR 0005).

## 9. Modelos de domínio (Pydantic)

- `BaseModel` com campos **camelCase espelhando o JSON da entidade** (`apiVersion`, `revisionNumber`, `accessToken`) — identificadores de código (variáveis locais, parâmetros, atributos de serviços) seguem PEP 8 `snake_case`; tipos completos (`List[str]`, `Optional[datetime]`).
- Campos calculados/preenchidos automaticamente usam `model_post_init` (ex.: `expires_at = now(UTC) + expires_in` em `LoginSession`); métodos auxiliares no próprio model (`is_expired(now)`).
- Timestamps **timezone-aware em UTC** (`datetime.now(timezone.utc)`); serialização preferida `model_dump_json()` / `model_validate_json()`.
- Persistência local sensível (padrão `SessionStore`, ADR 0006/0007): arquivo oculto **no diretório do pacote** (`PACKAGE_ROOT` — co-residente do `.sen`), escrita **atômica** (`mkstemp` → `fsync` → `chmod 0o600` → marcação de hidden no Windows → `os.replace`), deleção do temp em falha, e **mensagens de erro sem conteúdo da sessão**. Git-ignored via `.sen_session*`.

## 10. Testes

- Espelham a árvore de `src/` em `tests/unit/<camada>/...`; rodar com `poetry run pytest` (CI adiciona `--junitxml` + `--html`).
- Ferramentas do projeto: `pytest` + `CliRunner` (Typer) + `monkeypatch` + `@pytest.mark.parametrize` + fixtures `autouse` para isolar `Settings` das fontes de env do host.
- Doubles **feitos à mão** (classe `FakeService`/`RecordingService` retornando models reais) — sem biblioteca de mocks externa.
- Convenções de asserção características:
  - mensagens/frases literais de UX aparecem na saída (`"Login realizado com sucesso." in result.output`);
  - **segredos NUNCA aparecem** (`assert TOKEN not in result.output`);
  - códigos de saída são parte do contrato (`assert result.exit_code == 2`).
- Nomes de teste descrevem o cenário: `test_login_success_prints_summary_without_secrets`, `test_login_categories_map_to_exit_codes`.

## 11. Segurança e privacidade (transversal)

- Nenhum segredo, credencial ou token real em código, testes, fixtures ou `docs/` (regra explícita do `docs/README.md`).
- Blobs fake em testes (`QUJDREVG`, tokens dummy).
- `.env`, `.sen`, `.sen_session*`, `external-repo/`, `logs/*.log` e caches ficam no `.gitignore` — com **comentário referenciando o ADR** responsável (veja `.gitignore` l.160; o gabarito `.sen.example` permanece trackeado — ADR 0007).
- Erros de usuário jamais incluem valores de credencial, mesmo truncados.

## 12. Documentação interna e OpenSpec

- `docs/README.md` é o índice; a pasta registra decisões do **orquestrador**, enquanto o canônico fica no Confluence/`Plataforma-Sensedia/API Ops` (prevalece o canônico em conflito).
- **ADRs** (`docs/adr/NNNN-titulo-em-pt-br-com-hifen.md`), formato MADR, um por decisão: cabeçalho + tabela (`Status`, `Data`, `Supersede`, `Correlatos`), seções fixas `Contexto`, `Decisão`, `Alternativas consideradas e rejeitadas` (tabela motivo), `Consequências` (positivas/negativas), `Fontes` (citar código, datas e origem da confirmação). PT-BR.
- **Feature specs** em `docs/features/<feature>.md` (ex.: `sen-login.md`).
- Mudanças planejadas passam por **OpenSpec** (`openspec/changes/<kebab-case>/` com `proposal.md`, `design.md`, `tasks.md`, `specs/*/spec.md` + archive datado `2026-09-16-…`) — gerar via CLI (`npx openspec new change …`) e não à mão.
- `CHANGELOG.md` mantido manualmente (entradas `data — Área — título — autor — tipo`); recomendação registrada no próprio arquivo: adotar **Conventional Commits**.

## 13. Git e CI (Bitbucket Pipelines)

- Branch principal de trabalho: `develop`; merges para `release` disparam a esteira (`bitbucket-pipelines.yml`): instalar Poetry → `poetry install` → clonar `sensedia/apis-repo` em `./external-repo` → gerar `.env` a partir de variáveis protegidas do repositório → rodar a aplicação → `pytest` com relatórios em `test-results/` publicados como artifacts.
- Credenciais da esteira vêm de variáveis protegidas (ex.: `BB_USERNAME`, `BB_REPO_TOKEN`), nunca versionadas.
- Nomes de PR/merge históricos usam tickets tipo `APIO-XX-descricao` (ver `CHANGELOG.md`).
- Convenção de commits (Conventional Commits) e demais boas práticas de desenvolvimento são mantidas na wiki interna Nexus: [Boas Práticas de Desenvolvimento](https://sensedia.atlassian.net/wiki/spaces/Nexus/pages/5229838371/Boas+Pr%C3%A1ticas+de+Desenvolvimento) — consulte por lá para padrões atualizados de prefixos e mensagens de commit.

## 14. Divergências abertas a considerar (não tratar como padrão)

Registradas aqui para transparência; em novos módulos, siga o padrão indicado, não a exceção:

- **Versão do Python:** README diz "3.10+", Poetry exige `^3.12`, CI/Docker usam 3.12 → tratar **3.12** como alvo.
- **`CMD` do Dockerfile** ainda aponta para módulo placeholder (`apiops_cli_exemplo`) e o `LABEL version` está descolado do `pyproject` (`0.1.0`) — ajustar ao versionar imagens reais.
- **`bitbucket-pipelines.yml`** tem bloco `artifacts` duplicado/indentado incorretamente no passo atual — validar antes de editar.
- **`setup_logging()` ainda não é chamado no entrypoint** (ADR 0005 aponta como wire obrigatório pendente).
- **Par `OAUTH_CLIENT_ID/OAUTH_CLIENT_SECRET` é transitório** — novos fluxos devem usar `SEN_CREDENTIALS` (ADR 0004).
- **Perfis de execução**: além do host do dev, há dois alvos de desenho — esteira (CLI headless, envs injetadas, exec terminada ao fim do comando) e **executável distribuído ao dev**; por isso as credenciais do `sen login` sairão do `.env` e irão para um `.sen` colocado junto ao pacote entregue (detalhado em §4.3).

---

*Como contribuir: alterou um padrão? Atualize este documento E abra/trace um ADR (§12) citando-o nos Correlatos.*
