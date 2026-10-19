## 1. Configuração e credencial

- [x] 1.1 Adicionar em `Settings`: `SEN_CREDENTIALS` (opcional), `AUTH_HOST` e `AUTH_LOGIN_PATH` (**obrigatórias, sem fallback/default**); atualizar `.env.example` com as variáveis + instrução de geração do blob Base64. Campos legados (HOST/OAUTH_*/API_ID/REQUEST_TIMEOUT) permanecem obrigatórios no pydantic. Verificar: pytest de `Settings` (valores carregados + obrigatórias sem fallback); `AUTH_LOGIN_PATH` vazio → erro categorizado pré-rede.
- [x] 1.2 Implementar resolução da credencial (função pura): `SEN_CREDENTIALS` é a única fonte — ausente/vazia → erro categorizado "credencial não encontrada" pré-rede. Verificar: testes unitários (presente usada intacta; ausente → erro; par `OAUTH_*` presente porém ignorado pelo `sen login`).

## 2. Domínio

- [x] 2.1 Criar `domain/models/login_session_model.py` (`LoginSession`): `access_token`, `token_type`, `expires_in`, `user_groups`, `user_email`, `username` + `expires_at` (UTC) calculado em `model_post_init`; serialização com `model_dump_json`. Verificar: teste com a resposta real demonstrada da API 400 conferindo `expires_at` = recepção + `expires_in`.

## 3. Adapter outbound

- [x] 3.1 Criar `domain/ports/orchestrator_auth_port.py` (`OrchestratorAuthPort.login(credential_b64: str) -> dict`) e adapter em `adapters/outbound/http/orchestrator_auth_api/` montando URL exclusivamente por `AUTH_HOST` + `AUTH_LOGIN_PATH` (obrigatórias, sem fallback), header `Authorization: Basic {blob}` (intacto, sem construção local), payload `{"grantType": "client_credentials", "scope": "apis/all"}`, reusando `HttpClient`. Verificar: unitários com `HttpClient.request` mockado afirmam URL, método POST, header e payload.
- [x] 3.2 Propagar erros HTTP do tratamento existente (401/403 vs 5xx) como falhas categorizadas pelo serviço. Verificar: teste do adapter com `HttpClient` mockado produzindo exit para 4xx e exceção para 5xx esgotado.

## 4. Storage seguro da sessão

- [x] 4.1 Criar módulo em `infrastructure/secure_storage/`: escrita atômica (provisório + `os.replace`) em `tempfile.gettempdir()/.sen_session`, `chmod 0o600` (POSIX), atributo oculto best-effort no Windows, substituição sem resíduos; expor também o **leitor** com validação de expiração (`expires_at`) para execuções futuras. Verificar: testes (tmp_path) de escrita, substituição, modo POSIX, leitura de sessão válida e de sessão expirada tratada como ausente.
- [x] 4.2 Tratar falha de I/O como erro categorizado de persistência, sem ecoar conteúdo. Verificar: teste simulando erro de rename/permissão → exceção categorizada com mensagem sanitizada.

## 5. Serviço de login

- [x] 5.1 Criar `application/services/login_service.py`: validar credencial (pré-rede) → adapter → validar campos obrigatórios (protocolo, campo faltante nomeado) → persistir → retornar sessão sanitizada; taxonomia/exit codes (2 credencial, 3 recusada, 4 protocolo, 5 persistência). Verificar: testes do serviço com portas falsas cobrindo cada cenário da spec (`cli-auth`).
- [x] 5.2 Instrumentar eventos `auth.login.started|success|failure` + `auth.credentials.source` via módulo de observabilidade existente, sem valores sensíveis. Verificar: testes capturando logs (caplog) afirmam eventos e ausência de credencial/token em qualquer linha.

## 6. CLI e composição

- [x] 6.1 Registrar `@sen_app.command("login")` em `cli_adapter.py` traduzindo categoria → mensagem Rich amigável e exit code; saída de sucesso exibe username/e-mail/grupos/expiração apenas. Verificar: testes da CLI (runner Typer) para os cenários da spec sem rede (serviço falso).
- [x] 6.2 Ajustar `main.py` com gate mínimo por argv: modo bare (sem argumentos) mantém o fluxo atual íntegro; modo `sen <cmd>` pula o preprocessamento e injeta somente o necessário no `ctx.obj`. Verificar: unitários de gate com `monkeypatch.setattr(sys, "argv", [...])` para os três casos (vazio, login, list api); pipeline `release` rodando verde no smoke.

## 7. Documentação e qualidade

- [x] 7.1 Atualizar `README.md` (seção do comando `sen login`, credencial única e fonte `SEN_CREDENTIALS`, exit codes, localização do arquivo de sessão) e nota de privacidade do arquivo. Verificar: revisão textual; exemplos do README reproduzíveis manualmente.
- [x] 7.2 Rodar `pytest` (suite existente 100% verde + novos testes), `ruff`, `black` e `mypy`. Verificar: comandos `poetry run pytest`, `poetry run ruff check .`, `poetry run mypy src` sem erros.
- [x] 7.3 Validar a mudança no OpenSpec: `openspec validate add-sen-login --strict`. Verificar: validação sem erros; cenários mapeados 1:1 com testes nos itens acima.
