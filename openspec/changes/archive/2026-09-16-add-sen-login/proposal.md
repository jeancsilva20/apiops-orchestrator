## Why

A CLI `sen` autentica hoje de forma implícita (fluxo LEGACY executado durante o import do `main.py`), sem comando explícito de login e sem persistir a sessão. Esta mudança entrega **somente** o comando `sen login` (primeira fase da autenticação): ler a credencial Basic de `SEN_CREDENTIALS`, chamar a Orchestrator Auth API num endpoint configurável e guardar a sessão em arquivo local que a própria aplicação consiga ler nas execuções seguintes — base para as fases seguintes (guard por scopes, grant efêmero).

## What Changes

- Novo comando `sen login` registrado no CLI (`sen_app`).
- Credencial Basic com **única fonte** na variável **`SEN_CREDENTIALS`** (`Base64(client_id:secret)`), enviada **intacta** ao endpoint (ADR 0001). Sem fallback: se a credencial não estiver disponível, o login falha com erro categorizado "credencial não encontrada" antes de qualquer chamada de rede. O par `OAUTH_CLIENT_ID`/`OAUTH_CLIENT_SECRET` continua usado **apenas** pelo fluxo LEGACY existente, que não é alterado.
- Endpoint de autenticação **parametrizável e totalmente obrigatório**: settings `AUTH_HOST` e `AUTH_LOGIN_PATH` (sem fallback para `HOST`, sem default em código) — variáveis de login não configuradas falham antes de qualquer chamada de rede. Alvo atual: `https://api-consulting.sensedia.com` + `/cli-2/orq-auth/v1/oauth2/token`.
- Novo modelo de domínio `LoginSession` (`access_token`, `token_type`, `expires_at` derivado de `expires_in`, `user_groups`, `user_email`, `username`).
- **Sessão persistida em arquivo oculto local** (dir temporário do SO, escrita atômica, permissões restritivas), com leitor para execuções posteriores — token/perfil jamais impressos em stdout ou logs.
- Ajuste **mínimo** de composição em `main.py` (gate por argv) para permitir dispatch standalone do comando; modo bare da esteira preserva o comportamento atual.
- Padrões existentes respeitados: `HttpClient` compartilhado (retry 5xx, RFC 7807), logs de observabilidade (eventos `auth.*`, ADR 0005), saída Rich.
- Atualização de `.env.example` e `README.md`.

Sem alteração no comportamento dos comandos já existentes (`sen list api` segue igual) e sem alteração do fluxo LEGACY.

## Capabilities

### New Capabilities
- `cli-auth`: Autenticação e gestão de sessão local da CLI — comando `sen login` (leitura da credencial Basic, chamada ao endpoint parametrizável, mapeamento da resposta para `LoginSession`) e persistência segura da sessão em arquivo oculto legível por execuções futuras.

### Modified Capabilities
<!-- Nenhuma: não há specs existentes neste projeto e nenhum requisito de spec atual muda. -->
- (nenhuma)

## Impact

- **Código**: ajuste mínimo em `main.py` (gate por argv), registro do comando em `adapters/inbound/cli/cli_adapter.py`, novas variáveis em `config/settings.py`, novo adapter/porta para a Orchestrator Auth API, `LoginSession` no domínio, serviço de login e módulo de storage seguro (escrita + leitura com validação de expiração).
- **Configuração**: `.env.example` ganha `SEN_CREDENTIALS`, `AUTH_HOST`, `AUTH_LOGIN_PATH` (opcionais/defaults — os campos legados do `Settings` permanecem obrigatórios, inalterados).
- **Dependências**: nenhuma nova (Typer, requests e pydantic já presentes).
- **Externo**: dependerá do endpoint da Orchestrator Auth API operacional (resposta demonstrada pelo time: `access_token`, `token_type`, `expires_in`, `user_groups`, `user_email`, `username`).
- **Observabilidade**: logs seguindo ADR 0005 (eventos `auth.*`, zero segredos).
