## Why

O desenho de distribuição aprovado (§4.3 da doc de padrões e o backlog de credenciais da fase 1) define dois perfis de execução: **esteira** (CLI headless, `.env` gerado em runtime a partir de secrets) e **executável entregue ao dev**, que deve ler suas credenciais de um arquivo **`.sen` colocado junto ao pacote** — hoje a CLI só sabe ler o `.env` da raiz do repositório, inexistente no pacote distribuído. Além disso, o `.sen_session` é gravado no **diretório temporário do OS** (`tempfile.gettempdir()` em `session_store.py`), invisível ao dev e volátil, enquanto o desejo registrado é tê-lo na mesma pasta do `.sen`, oculto e previsível. A change `add-sen-entrypoint` deixou este escopo deliberadamente para fora ("onde as credenciais vivem é outro change") — este é esse change.

## What Changes

- Criação do conceito de **diretório do pacote** (`PACKAGE_ROOT`) nas `Settings`: no modo dev equivale a `src/apiops_orchestrator/`; é o ancoradouro de ambos os arquivos e o alvo natural do diretório do binário quando houver distribuição congelada (registrado como limitação atual).
- **`.sen` como arquivo de credenciais de login do pacote** (sintaxe dotenv, ao lado do entrypoint): recebe **juntos** `SEN_CREDENTIALS`, `AUTH_HOST` e `AUTH_LOGIN_PATH` — **nenhum dos três com default/fallback em código** (auditado no estado atual). Precedência proposta: **`.sen` sobre `.env`**; variáveis de processo continuam acima de ambos (comportamento nativo pydantic-settings, `env_file` múltiplo).
- **Relocalização do `.sen_session`** de `tempfile.gettempdir()` para o mesmo diretório do pacote (junto ao `.sen`), mantendo escrita atômica, marcação de hidden e parâmetro `directory` para testes.
- **Mensagens de credencial ausente atualizadas** para orientar as duas fontes possíveis (variável ambiente ou `.sen`).
- `.gitignore` ampliado (`.sen` exato + variantes de sessão), **gabarito `.sen.example` versionado** (seguindo o molde de comentários do `.env.example`) e atualização de `docs/features/sen-login.md` + ADR novo de fontes de configuração.
- Migração de credencial é **opcional e progressiva**: nenhum usuário existente quebra — quem só tem `.env` continua funcionando idêntico.

## Capabilities

### New Capabilities
<!-- Nenhuma: é evolução da capability `cli-auth` (fontes de credencial + persistência de sessão). -->
- (nenhuma)

### Modified Capabilities
- `cli-auth`:
  - MODIFIED **Credencial Basic como única fonte** — a credencial ganha segunda origem materializada: arquivo `.sen` (valor continuar intacto como conteúdo de `SEN_CREDENTIALS`; a invariante "sem fallback OAUTH" permanece).
  - MODIFIED **Sessão persistida em arquivo e legível por execuções posteriores** — o diretório do arquivo de sessão passa a ser o **diretório do pacote** (junho do `.sen`), não mais a raiz do projeto/tempdir; todos os cenários originais preservados com o novo endereço.
  - ADDED **Arquivo `.sen` como configuração da CLI** — formato, localização, precedência sobre `.sen`→`.env`→processo (processo vence), exclusão do versionamento e inexistência de segredo em gabarito.

## Impact

- **Código**: `config/settings.py` (múltiplos `env_file`, `PACKAGE_ROOT`), `infrastructure/secure_storage/session_store.py` (diretório default), `application/services/login_service.py` (apenas texto da mensagem de credencial ausente).
- **Config/repo**: `.gitignore` (+`.sen`, ajuste do padrão de sessão para o novo diretório), novo `.sen.example`.
- **Esteira**: sem quebra — `.env` gerado em runtime continua suportado (precedência menor que `.sen`, que lá não existe).
- **Docs**: `docs/features/sen-login.md`, novo ADR (fontes de credencial) e tabela §4.3 da doc de padrões.
- **Testes**: fixtures de settings para precedência multi-arquivo; store tests já isolados por `directory=tmp_path` (baixo risco).
- **Dependências**: nenhuma nova.
