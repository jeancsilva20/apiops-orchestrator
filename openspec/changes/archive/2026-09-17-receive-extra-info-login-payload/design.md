## Context

A rota `POST /orq-auth/v1/oauth2/token` (API 400, Plataforma de Consulting — inspeção registrada em `docs/auth/api-orq-auth-contrato.md`) recebeu um interceptor que injeta, em respostas HTTP 200, o bloco `extra_info` com dois perfis mutuamente exclusivos:

- **super-admin** (`$call.contextVariables.get("user-super-admin") == true`):
  `extra_info = {source: "pipeline", profile: "super-admin", scope: "admin", admin_access_token: <bearer>}`
- **developer**: injeta `user_name`, `user_email`, `user_groups` (CSV/lista normalizada) e `scope` recuperados das context variables; a plataforma devolverá explicitamente `profile: "developer"` para o perfil dev.

O orquestrador hoje (faltou acompanhar o ajuste da rota) espera o formato flat antigo no topo do JSON — `REQUIRED_SESSION_FIELDS = (access_token, token_type, expires_in, user_groups, user_email, username)` em `login_service.py` — e serializa `LoginSession` tal como veio para o `.sen_session`. Consequências sem ação: todo login dev quebra em `LoginProtocolError`, o `scope` (insumo do guard local previsto nos ADRs 0002/0003) não é capturado e não existe tratamento para a sessão super-admin da esteira.

Decisões já firmadas com o dono da demanda (17/09/2026):

1. Developer exige **todos** os campos (inclusive `scope` e `user_groups` **não-vazio**).
2. `admin_access_token` **não vai para o disco** — esteira é efêmera e consome o token na mesma execução.
3. Discriminação **pelo campo `profile`** (não inferência por presença de `admin_access_token`); perfil vazio/desconhecido interrompe o fluxo com erro.

## Goals / Non-Goals

**Goals:**

- Adaptar o parse do login ao envelope `extra_info` com validação de campos **por perfil**.
- Manter erros categorizados e genéricos ao usuário (`LoginProtocolError` sem ecoar payload) — terreno preparado para o débito de erros genéricos.
- Persistir `profile` e `scope` no arquivo de sessão; manter `admin_access_token` exclusivamente em memória na execução corrente.
- Cabeçalho de sessão legível por execuções posteriores do jeito previsto na spec, com sustentação por testes de contrato (fixtures dos dois perfis).

**Non-Goals:**

- Alterar `OrchestratorAuthAdapter`, endpoints, retries ou o tratamento HTTP compartilhado.
- Implementar o guard de fase 2 (consumo do `scope` em decisões de autorização por ação) — este change só garante que o dado estará salvo.
- Implementar `POST /oauth2/token/validation` ou trocar tokens no fluxo dev→admin.
- Mudar a localização/higiene do arquivo de sessão (spec vigente mantida).

## Decisions

### D1 — Discriminação de perfil pelo campo `extra_info.profile`

O desenho adotado é o próprio protocolo declarar o perfil: `profile == "super-admin"` | `profile == "developer"`. Qualquer outro valor — incluindo ausência — é erro fatal do login.

- **Alternativa descartada** (inferir por presença de `admin_access_token`): mais tolerante a drift do interceptor, mas transforma a ausência de um campo em contrato. O interceptor já devolve `profile` e o dono da decodificação é a mesma equipe que ajusta a rota; explícito vale mais que heuristicamente resiliente.

### D2 — Matriz de validação por perfil centralizada no service

`_parse_response` passa a operar em duas etapas: (a) núcleo comum — `access_token`, `token_type == Bearer`, `expires_in`, `extra_info` como dict, `profile` com valor conhecido; (b) perfil — itera a matriz obrigatória do perfil sobre `extra_info`. Falta de campo ⇒ `LoginProtocolError` com mensagem genérica ("Resposta de login incompleta/incompatível."), detalhes completos só em log `logger.error` interno.

- Estrutura: `PROFILE_REQUIRED_FIELDS: Mapping[str, tuple[str, ...]]` no módulo, novas entradas implicam tocar um único ponto.
- **Alternativa descartada** (modelos Pydantic separados + union discriminada): daria rigor de tipagem de graça, mas complica o `SessionStore` (dispatch de classe no load/save) e o resumo do CLI para ganho marginal num modelo tão pequeno.

### D3 — `LoginSession` único com campos condicionais e helpers de perfil

Um modelo: `profile` (literal), `scope`, campos condicionais opcionais (`username`, `user_email`, `user_groups`, `admin_access_token`) e propriedade `is_super_admin`. Guardas de consistência no `model_post_init` impedem combinações impossíveis (ex.: dev sem username; super-admin sem `admin_access_token`).

### D4 — `admin_access_token` vive em memória; disco o omite

O `SessionStore.save` serializa `model_dump(exclude={"admin_access_token"})` quando `profile == "super-admin"`; o load entende a ausência como estado válido (token indisponível nesta execução). Na prática a esteira roda `sen` pelado: login + ações in-process, sem persistência do token privilegiado.

- **Alternativa descartada** (persistir no `.sen_session`, afinal o arquivo já é oculto com permissões restritas): manteria o token de escopo `admin` em disco entre execuções, acima do ciclo de vida efêmero pretendido e elevando o impacto de qualquer incidente de I/O cópia/backup.

### D5 — Erro permanece silencioso quanto ao corpo

Mensagens ao usuário seguem genéricas e categorizadas (padrão já praticado: credencial recusada × indisponibilidade). Detalhe de campo faltante/tipo incorreto segue para log interno apenas.

### D6 — Sessão de perfil ignorada na leitura (defesa contra downgrade)

Ao carregar sessão gravada **sem** `profile` (arquivo do formato antigo) ou com perfil desconhecido, o store a trata como ausente ⇒ cadeia de logout/execução aciona re-login em vez de transitar sessão malformada.

## Risks / Trade-offs

- [Interceptor enviar shapes divergentes por ambiente (Consult × ECAD)] → Fixtures de contrato por perfil cobrem os casos de aceitação; divergência vira `LoginProtocolError` determinística e não segfault silencioso do fluxo.
- [`user_groups` vazio para dev bloqueando pipelines de apps sem grupo] → Decisão do dono: obrigatório não-vazio. Se um dia houver exceção, relaxa-se a matriz em D2 (um ponto de mudança).
- [`admin_access_token` requerido em outra execução/re-execução subsequente não existirá em disco] → Assumido (esteira efêmera); execução posterior refaz o fluxo de auth; fase 2 usa `/validation` para gerar token efêmero por ação.
- [Perfil novo futuro (ex.: auditor)] → `profile` desconhecido falha fechado; ampliação é inclusão na matriz + literal do modelo, com testes de contrato próprios.
- [Mensagem genérica pode dificultar diagnóstico pelos devs da equipe] → Logs internos carregam o detalhe completo (campo/perfil) sem alterar a superfície do usuário.

## Migration Plan

1. Code-first atrás do change spec, fixtures novos e suite verde (contract + unit).
2. Deploy junto com a go-live do interceptor na rota (ordem plataforma → esteira/consoles).
3. Rollback: reversão da release do orquestrador restaura parser flat antigo, compatível com a rota que ainda não publica `extra_info`.

## Open Questions

- (nenhuma — decisões D1–D6 aprovadas com o dono; o formato exato de `scope` dev (string) e `user_groups` (lista/string-CSV) já é normalizado no interceptor)
