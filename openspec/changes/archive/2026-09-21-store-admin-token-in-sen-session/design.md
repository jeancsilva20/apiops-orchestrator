# Design: store-admin-token-in-sen-session

## Context

- Contrato atual (spec `cli-auth`, requirement "Sessão persistida em arquivo e legível por execuções posteriores"): `SHALL NOT conter adminAccessToken`; `SessionStore.save()`materializa isso com `model_dump_json(exclude={"adminAccessToken"})` e comentário "memory only".
- Uso real detectado: esteira = login super-admin em um processo + comandos em processos seguintes → o token privilegiado precisa sobreviver entre eles, senão cada comando re-autentica (ou fica dependente de credencial de super admin em `.sen` indefinidamente).
- Salvaguardas já existentes no arquivo de sessão: escrita atômica, permissões restritivas + marca hidden no Windows, exclusão do versionamento (`.sen_session*`), carregamento por `expiresAt` (sessão expirada = ausente), rejeição de sessão malformada.

## Goals / Non-Goals

**Goals:**
- `.sen_session` de perfil `super-admin` contém `adminAccessToken`; `developer` permanece sem o campo (estado guardado do modelo garante).
- Carregamento subsequente devolve a sessão completa para super-admin (incl. token), com expiração e validação de perfil intactas.
- Rastro documental: revisão registrada no ADR 0002 (ponto específico da proibição de persistência), sem rewrite do ADR.

**Non-Goals:**
- Consumo do token pelo `sen list` / esteira (provider atual segue com `ADMIN_SEN_CREDENTIALS` até a leva de integração — mudança separada).
- Guard de escopo, rotação, TTL adicional, criptografia at-rest do arquivo (décision thread existente — backlog de distribuição de credenciais).
- Qualquer mudança no fluxo `sen login` (roteiro, mensagens, persistência de acesso dev).

## Decisions

**D1 — Persistência condicionada ao perfil, não à chamada.** O `exclude` do `save()` vira inclusão natural (serialização do modelo completo); quem garante presença/ausência é o estado guardado do modelo (`LoginSession._ensure_guarded_state`: developer SEM adminAccessToken; super-admin COM). Motivo: uma única fonte de verdade (o guard do modelo), zero lógica nova no store. Alternativa descartada: bifurcar serialização por perfil no store — duplicaria a regra do modelo.

**D2 — Supersede pontual e documentado do ADR 0002.** O ADR permanece como visão de ciclo de vida (emissor/authority/guards), mas seu ponto "superadmin: nada em arquivo" é revisado: agora NADA além do `.sen_session` (mesma ACL/restrictões da sessão dev). Nota de revisão com data e link do change.

**D3 — Compat de carga em ambas as direções.** `load()` tolera: (i) sessão super-admin COM token (novo formato), (ii) super-admin SEM token (arquivo anterior ao change — não apagar, apenas administrador sabedor re-loga), (iii) malformed/sem profile → ausente (regra existente). Developer sem campo carrega como hoje.

**D4 — Higiene inalterada:** nenhum fragmento de token em logs/exceptions/saídas (ADR 0005); testes AAA sem valores reais (blobs dummy tipo `QUJDREVG`).

## Risks / Trade-offs

- [Arquivo de sessão passa a valer mais (token privilegiado em disco)] → salvaguardas de arquivo já estabelecidas (permissão, gitignore, atomicidade) + máquina do runner é o trust boundary assumido da esteira; mitigação futura possível (criptografia/keyring) permanece no backlog de distribuição de credenciais, fora desta leva.
- [Senhas velhas do arquivo (super-admin sem token) lembradas como válidas] → `load()` aceita e retorna (compat); consumo decidirá política (aceitar campos presentes; re-login se o consumer exigir token ausente). Contrato registrado no delta.
- [Confusão entre credencial (`.sen`) e token (`.sen_session`)] → convenção já separada por arquivo + nomenclatura; README/backlog ganha nota na leva de consumo.

## Migration Plan

1. Delta de spec MODIFIED (este change) aprovado.
2. Alterar `SessionStore.save`/`load` + docstring do modelo + comentários.
3. Ajustar/estender testes de `session_store` (super-admin contém/recarrega; developer não contém; legado sem token carrega).
4. Nota de revisão no ADR 0002 + CHANGELOG.
5. Rollback: git revert da leva — formato de arquivo extra campo é tolerado pelo loader atual (ignora extras) desde que a leitura não valide estritamente campos desconhecidos (verificar `load()` — pydantic ignora extras por configuração atual).

## Open Questions

- Nenhuma bloqueante. Consumo do token pelo `sen list` (substituição definitiva do `ADMIN_SEN_CREDENTIALS` na esteira) fica para a change de integração, separada.
