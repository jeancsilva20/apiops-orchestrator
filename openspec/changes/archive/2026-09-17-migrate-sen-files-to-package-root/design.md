## Context

Dois problemas de residência de arquivos se interceptam nesta mudança: (1) a **credencial** — hoje, exclusivamente ambiente/arquivo `.env` da raiz do repositório, incompatível com o executável a distribuir; (2) a **sessão** — hoje gravada em `tempfile.gettempdir()`, volátil entre máquinas/contextos e fora do alcance visual do dev, quando o desejado é convivê-la com o `.sen` na pasta do pacote. A rota/protocolo de login, o parse por perfil e o fluxo de erros recentemente especificados (`receive-extra-info-login-payload`, arquivado) não são alterados.

## Goals / Non-Goals

- Goals: fonte de credencial legível pelo pacote distribuído (`.sen`); sessão co-locada e oculta junto ao `.sen`; precedência determinística entre fontes; zero quebra para quem usa só `.env`; segredos sempre fora do Git.
- Non-Goals: adaptação definitiva a executável congelado (`sys._MEIPASS`/diretório do `.exe`) — registrada como limitação e follow-up; migração da esteira para secrets nativos sem `.env`; mudanças no handshake de login ou no formato da sessão.

## Decisions

- **D1 — Precedência de fontes: processo > `.sen` > `.env`.** Implementada via `SettingsConfigDict(env_file=(ENV_PATH, SEN_PATH))` — em pydantic-settings, arquivos posteriores na tupla vencem anteriores, e variáveis de processo vencem qualquer arquivo. Racional: a esteira não terá `.sen` (segue 100% `.env`/secrets), e o dev com os dois arquivos presente merece que o `.sen` — associado ao pacote — mande. Alternativa rejeitada: resolver manualmente quais chaves vêm de qual arquivo (mais controle, muito mais código e superfície de erro; ganho nulo ao desenho).
- **D2 — `PACKAGE_ROOT` derivado do módulo, expondo o caminho.** `PACKAGE_ROOT = Path(__file__).resolve().parents[1]` (equivale a `…/src/apiops_orchestrator`) e campo público `PACKAGE_ROOT: Path` no `Settings`. Em dev, é a pasta `src/apiops_orchestrator` pedida pelo to-do; num futuro binário congelado, apontaremos para o diretório do executável (follow-up deliberado — ver Limitações). Alternativa rejeitada: acoplar a `cwd` ou a `PROJECT_ROOT` (ambos quebram a premissa do executável distribuído que motivou esta mudança).
- **D3 — `.sen` = bloco de credenciais de login, definitivo: `SEN_CREDENTIALS`, `AUTH_HOST`, `AUTH_LOGIN_PATH`.** As três configuram a autenticação e migram **juntos** para o arquivo do pacote — é o conjunto sem o qual o executável não autentica; chaves extras são ignoradas (`extra="ignore"` já vigia), então estender depois é aditivo. **Nenhum dos três SHALL ter default/fallback em código** — auditado no estado atual: `Settings` declara `AUTH_HOST`/`AUTH_LOGIN_PATH` obrigatórios sem default e `build_login_url` falha com `RuntimeError` antes de rede; `SEN_CREDENTIALS` usa falha tardia categorizada (`CredentialNotFoundError` pré-rede) — o default `None` não constitui fallback (nunca substitui valor; apenas adia o erro). Gabarito `.sen.example` versionado com comentários, replicando o molde de geração do `.env.example`. Alternativa considerada: `.sen` carregando TODA a configuração (HOST, API_ID, REQUEST_TIMEOUT…) — rejeitada por ora: expõe ao dev variáveis que pertencem à esteira e amplia o contrato sem necessidade registrada.
- **D4 — Nome da sessão mantido: `.sen_session`** (underscore, como no código e no `.gitignore` atual). O Slack usa hífen, mas renomear seria churn de arquivo/permisssões/documentação sem ganho funcional registrado. `SESSION_FILE_NAME` segue a constante única.
- **D5 — Mensagem de credencial orientada ao `.sen` (mono-fonte).** `CredentialNotFoundError` diz: defina `SEN_CREDENTIALS` no arquivo `.sen` do diretório do aplicativo — decisão do Isaac (17/09): o texto guia SOMENTE para o `.sen`, sem instruções paralelas de variável de ambiente (a mecânica de precedência continua aceitando processo/`.env`; apenas a orientação ao usuário é única e apontando para a casa nova). Texto PT-BR acionável, sem mencionar `OAUTH_*`.
- **D6 — Tesoura no escopo de specs.** Somente cláusulas de *localização/fonte* mudam. Requisito de exclusão de versionamento ganha cobertura do `.sen`; cenários intactos são recopiados íntegros na delta MODIFIED.

## Risks / Trade-offs

- **[`.sen` ignorado por `.gitignore` largo]** → padrão `.gitignore` por match **exato** (`.sen`) + variantes `.sen_session*`/temporárias — gabarito `.sen.example` continua trackeado.
- **[Windows: pastas de pacote sem marcação de hidden]** → marcação de hidden é apenas-best-effort no arquivo; o `.sen_session` continua discretamente oculto por nome de ponto. Documentado.
- **[Duplo arquivo aumenta confusão "quem mandou?"]** → logs de inicialização (chave `config.sources.active`) informam a fonte efetiva do bloco de AUTH, sem valores.
- **[Tempdir migrado: sessões antigas órfãs]** → comportamento aceitável e desejado (sessão antiga simplemente ignorada; novo `sen login` repovoa o destino novo — sem migração silenciosa, coerente com D6 do change anterior).

## Migration Plan

1. Wiring de `PACKAGE_ROOT` + `env_file` múltiplo nas `Settings` (tests de contrato de settings primeiro).
2. `session_store.py` recebe diretório default do pacote; testes isolados via `directory=` seguem idênticos.
3. `.sen.example`, `.gitignore`, mensagens, docs e ADR — lote de fechamento.

## Open Questions (a homologar na revisão)

- ~~**OQ2**: `.sen` mínimo = bloco AUTH apenas (D3)~~ — **RESOLVIDO pelo Isaac (17/09)**: os 3 (`SEN_CREDENTIALS`, `AUTH_HOST`, `AUTH_LOGIN_PATH`) migram juntos; fallback auditado e inexistente no código.
- **OQ1**: precedência `.sen` > `.env` com processo no topo (D1) — confirma?
- **OQ3**: sessão continua `.sen_session` (D4) — ou alinhamos ao hífen do Slack (`.sen-session`)?
- **OQ4**: log de fontes ativas (`config.sources.active`) entra neste change ou fica pra depois?
