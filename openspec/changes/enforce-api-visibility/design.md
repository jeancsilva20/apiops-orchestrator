## Design

### Contexto

O `AdminTokenProvider` troca o token do dev por um token de super admin, e todas as chamadas ao Manager usam esse token. A rota de validação do `/orq-auth` recebe `{}`: não sabe qual API nem qual ação. A plataforma responde a qualquer API do tenant.

A regra de visibilidade existe em `domain/services/catalog_visibility.py` e é usada pela listagem do `sen list api`, filtrando cada página no cliente. O `CompletenessService` a aplica só para esconder nome e versão. O `ValidateService` recebe a sessão e não a usa. O drill-down do `sen list` e o `sen diag draft` não a aplicam.

### Decisões

**D1 — Uma regra só (`api-visibility`).**

| Condição | Visível para a sessão |
|---|---|
| sessão de super admin | tudo |
| `ORGANIZATION` | todos |
| `ME` | `owner` igual ao usuário **ou** usuário entre os da visibilidade |
| `GROUP` | nome do grupo igual a um dos grupos da sessão; `owner` e usuários não influem |
| tipo ausente ou desconhecido | nunca |

Comparações com trim, sem caixa e sem acento. É a regra que o código do `sen list` aplica hoje. O spec dizia que, no `ME`, só o `owner` contava e que `users[]` era irrelevante; prevalece o código, para que os quatro comandos concordem com o que a listagem já mostra (decisão do usuário em 21/10/2026).

**D2 — Duas fontes, uma visibilidade.** A plataforma entrega a visibilidade em dois formatos:

| Fonte | Comandos | Campos |
|---|---|---|
| catálogo (api-finder) | `list`, `completeness` | `contextType`, `owner`, `contextGroupName`, `contextUserLogins` |
| `GET /apis/{id}` | `validate`, `diag draft` | `visibility.visibilityType`, `visibility.owner`, `visibility.groupVisibility.name`, `visibility.users[].username` ([api-basic-info-campos.md](../../../docs/feat-api-estructure/api-basic-info-campos.md) §Visibilidade) |

Os dois viram o mesmo objeto de domínio, `ApiVisibility` (tipo, owner, grupo, usuários), e a regra só conhece esse objeto. O `validate` não faz chamada nova: usa o `GET /apis/{id}` da E2 (decisão do usuário em 21/10/2026).

**D3 — Super admin pelo perfil, não pelo modo.** A esteira faz login como super admin, então enxerga tudo sem exceção pelo `EXECUTION_MODE`. Sem sessão, a guarda mantém o comportamento atual da listagem (vê tudo). Na prática esse caso não ocorre: o token administrativo exige sessão.

**D4 — Invisível igual a inexistente.** Cada comando responde à API invisível com a mensagem e o exit code que já usa para a API inexistente, sem nome, versão, revisões ou qualquer outro dado dela:

| Comando | Mensagem | Exit |
|---|---|---|
| `sen list api --id X` (com ou sem `-r`) | "API X não encontrada ou sem permissão de acesso." (`ApiNotFound`, já existe) | `1` |
| `sen completeness` | "API X não encontrada ou sem permissão de acesso." (exceção nova da família do completeness) | `2` |
| `sen validate` | "API X não encontrada ou sem permissão de acesso. Nada foi publicado." (exceção nova) | `1` |
| `sen diag draft` | a mesma do `sen list` | `1` |

**D5 — Onde a verificação entra.** Logo depois da primeira leitura da API e antes de qualquer outra chamada sobre ela:

- `sen list api --id X`: após `list_api_detail`, antes do catálogo de workflows e das leituras de completeness;
- `sen completeness`: ver D6;
- `sen validate`: após o `GET /apis/{spec.id}`, antes da guarda de identidade, do `GET /revisions/{id}`, da leitura da API-template e do `PUT`;
- `sen diag draft`: após o `GET /apis/{spec.id}`, antes do `GET /revisions/{id}`.

No `validate` e no `diag draft`, o `404` desse `GET` passa a ser API inexistente, com a mesma resposta da invisível. Antes ele caía no erro interno — o que, com a regra nova, diria ao dev quais ids existem. A leitura fica numa função só, `api_visivel` em `validate_service.py`, usada pelos dois. (Achado no smoke de 21/10/2026.)

A API-template não passa pela regra: é o padrão da organização e o dev só a lê.

**D6 — `sen completeness` para sessão de dev.** A leitura é feita pelo id da revisão; o `--id` só servia à identidade. Por isso:

1. a consulta da API (`list_api_detail`) vem **antes** da leitura de completeness e é obrigatória;
2. API inexistente ou invisível encerra com a mensagem da D4, sem chamar `/revisions/{rid}/completeness`;
3. revisão fora de `revisions[]` da API encerra com a mensagem de revisão não encontrada que o comando já usa para o 404, exit `2`. Sem isso, `--id <API visível> --revision <revisão de outra API>` passaria;
4. falha da consulta encerra com exit `2` e a mensagem da família da falha, pela classificação compartilhada do Manager (`classify_manager_failure`; `404` conta como API inexistente): sem confirmar a permissão, o dado não aparece (decisão do usuário em 21/10/2026).

Para super admin, nada muda: a consulta continua tolerando falha e a revisão não é conferida contra a API.

Revoga em parte a D5 do `add-sen-completeness` (28/09/2026), que fazia a API invisível degradar como consulta falha e deixava a autorização com o servidor.

**D7 — Onde fica o código.**

```
domain/models/api_visibility_model.py      ApiVisibility (tipo, owner, grupo, usuários)
domain/models/api_catalog_model.py         ApiCatalogEntry.visibility() monta ApiVisibility dos campos que já tem
domain/services/api_visibility.py          visible_to(visibility, username, groups, super_admin) -> bool
                                           from_api_payload(api: dict) -> ApiVisibility
application/services/api_access_guard.py   ApiAccessGuard(session): sees_everything(), can_see(visibility)
```

- `api_visibility.py` substitui `catalog_visibility.py`: a regra deixa de ser só do catálogo.
- A leitura do `GET /apis/{id}` fica no domínio, como `domain/services/deployments.py` já faz com o mesmo payload.
- O adapter do catálogo não muda.
- A guarda devolve `bool`. Cada serviço lança a própria exceção, porque cada comando tem sua hierarquia e seu exit code — o mesmo arranjo de `classify_manager_failure`.
- Os serviços continuam recebendo a `LoginSession` e montam a guarda por dentro, como o `ValidateService` já monta `ReguaService` e `RevisionWriter`. Assim as factories e os testes que constroem os serviços não mudam. O `sen diag draft`, que não tem serviço, recebe a guarda pela `manager_api_factory`.
- O texto "API X não encontrada ou sem permissão de acesso." fica num só lugar, `API_NOT_FOUND_TEMPLATE` em `manager_failure_messages.py`, e as quatro respostas da D4 o usam.

**D8 — Fora do escopo.**

- `sen publish` e `sen deploy`: só rodam na esteira.
- Bloqueio de sessão de dev sem grupos: continua só na listagem, como hoje.
- `sen diag template`: só lê a API-template.

### Riscos

- **Formato do `visibility` no `GET /apis/{id}`.** Sondado em 21/10/2026 (só leitura, Manager de produção): `GROUP` traz `visibilityType`, `groupVisibility.name`, `owner` e `users: []`; `ORGANIZATION` traz `visibilityType` e `users: []`, sem `owner`. Os dois batem com o catálogo da mesma API. O tenant não tem API `ME` nem API com usuários na visibilidade; o item de `users[]` (`{id, username}`) vem do levantamento do basic info ([api-basic-info-criticidade-campos-omitidos.md](../../../docs/feat-api-estructure/api-basic-info-criticidade-campos-omitidos.md), "Usuários adicionais").
- **Completeness de dev mais restrito.** Com o catálogo fora do ar, o dev deixa de ver o completeness que antes via com campos `-`. É o efeito pedido pela decisão 4 da D6.

### Open Questions

Nenhuma.
