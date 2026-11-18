## Context

A CD chama o `sen deploy` depois que a CI gravou a revisão fixa do ambiente com o `sen publish`. O
deploy não grava conteúdo: coloca no ar, num ambiente do Manager, a revisão que já está gravada.

Restrições fechadas que não se renegociam aqui:

- publicar ≠ deployar; o caller CD não executa publish (memory bank, mapeamento e ADR-001);
- o dev não deploya pela CLI; toda promoção é pela esteira (decisão de 17/08/2026, ADR 0002);
- revisão alvo pelo número, nunca pelo id; criar revisão é ato humano (V-24, D-005 §9);
- deploy direto sobre deploy ativo, sem undeploy no fluxo padrão (memory bank, mapeamento);
- o relatório de deploy registra o estado anterior e o novo (backlog 06.02.02);
- o threshold é o do AG; o orquestrador não o define nem o altera (P10);
- HTTP 2xx não é prova de sucesso: conferir sempre (W-8).

Base empírica: [sondagem de 2026-10-19](../../../docs/feat-command-sen-deploy/sondagem-deployments-2026-10-19.md),
citada abaixo pelos ids dos testes (L-n, E-n, U-n).

## Goals / Non-Goals

**Goals:**

- Dar à CD um comando que coloca a revisão do ambiente no ar e devolve um veredito legível por máquina.
- Aplicar no CLI as guardas que a plataforma não aplica (E-3, E-5).

**Non-Goals:**

- Gravar conteúdo na revisão — é do `sen publish`.
- Rollback: depende da arquitetura decidir se o `sen deploy` passa a gravar a tag ou se o caller CD
  roda o publish antes (`techspec.md` §Questões em aberto; ADR-001 §Notas).
- Undeploy (`PUT /deployments/{id}`, U-3), smoke test, tag, pushback, concurrency e gatilhos.
- Correlation ID — change transversal a todos os comandos.

## Decisions

### 1. Fluxo

```
E0  configuração      EXECUTION_MODE · TARGET_REVISION_NUMBER · TARGET_ENVIRONMENT_ID   sem rede   exit 1
E1  manifesto         spec.id, version, basePath do api-basic-info.yaml                 sem rede   exit 1
E2  GET /apis/{id}    guarda de identidade (version, basePath)                                     exit 1
                      revisão pelo número, em revisions[] da própria API                           exit 1
                      ambiente em environments[] da API                                            exit 1
                      estado anterior do ambiente
E3  governança        stage da revisão: ambiente permitido, completeness, atributos               exit 3
E4  POST /deployments ESCRITA                                                           4xx/5xx → exit 1
E5  GET /apis/{id}    conferência                                                                  exit 1
```

E0 e E1 não usam rede: uma esteira mal configurada não deve gastar autenticação para descobrir isso.
Tudo até o E3 aborta **antes** da escrita.

### 2. Só na esteira

`EXECUTION_MODE=local` aborta no E0. Não há confirmação interativa: em `pipeline` não há quem
responda, e o comando não roda em outro modo.

### 3. Revisão alvo

`TARGET_REVISION_NUMBER` é obrigatória. O valor `1` é recusado — a Draft não é ambiente e não tem
deploy (V-24, glossário). Qualquer outro número é aceito se existir na API: o 4º ambiente ainda é
pendência (P1), e fixar 2/3/4 no código quebraria essa possibilidade sem ganho.

O `revisionId` vem **só** de `revisions[]` do `GET /apis/{spec.id}`. A resolução é do próprio deploy,
e não a do `RevisionWriter`, para que a mensagem de revisão inexistente liste número e id.
O `POST /deployments` aceita revisão de qualquer API do tenant (E-5): um id vindo de outra fonte faria
deploy de outra API.

### 4. Ambiente alvo por id

`TARGET_ENVIRONMENT_ID`, inteiro, configurado pelo DevOps em cada GitHub Environment. Id, e não
nome, porque o ambiente é do tenant e não da API: o mesmo `7` serve a todas as APIs, não quebra se o
ambiente for renomeado e não é ambíguo. O nome entra só na saída, lido de `environments[]`.

**Ambiente não ligado à API é recusado.** A plataforma aceita (E-3), mas aceitar transformaria um
erro de digitação na variável em deploy num ambiente errado. A mensagem lista os ambientes ligados,
com id e nome. Ligar a API ao ambiente é ato humano no Manager.

**Alternativa descartada:** nome do ambiente resolvido para id. Só ganharia legibilidade, que a
saída já entrega.

### 5. Estado anterior e conferência

Fonte: `revisions[].deployments` do `GET /apis/{id}`, filtrando `status == DEPLOYED` e
`environmentId` alvo. Estado anterior = esse registro antes do `POST` (ou nenhum). Conferência =
existe registro com o `id` devolvido pelo `POST`, `status == DEPLOYED`, `environmentId` e
`revisionId` alvo.

**Descartadas:** `GET /revisions/{id}` devolve `deployments: []` com a revisão no ar (L-2);
`environments[].revisionDeployed` só cobre ambientes ligados e não refletiu o deploy da E-3;
`GET /environments/{id}` devolve as variáveis do ambiente com valores em claro, inclusive
credenciais (L-5b), e **MUST NOT** ser chamado.

### 6. Gate do Adaptive Governance

O `POST` não aplica o gate (E-3), então o CLI aplica o que o **stage da revisão** configura. O
`workflowId`/`workflowStageId` vêm de `revisions[]` do mesmo `GET /apis/{id}`; o workflow vem de
`GET /api-governance/api/v3/workflows/{id}`.

| Critério | Regra | Leitura |
|---|---|---|
| Ambiente permitido | `environmentId ∈ deployableEnvironments`; **lista vazia = sem restrição** | workflow |
| Completeness | `completenessScore ≥ completenessRequisite`; requisito `0` não lê o completeness | `GET /revisions/{id}/completeness` |
| Atributos | `mustHave` presentes nos `apiTags` **do Manager** | `GovernancePrecheckService` |

Qualquer critério não satisfeito aborta com `exit 3`, listando todos os critérios violados — não só o
primeiro. DEV fica sem bloqueio de completeness porque o stage dele exige 0; HML e PRD bloqueiam
porque exigem 70 (P3, P10). O CLI não conhece esses números.

Os atributos vêm do Manager e não do repositório: o deploy coloca no ar o que está gravado, e foi o
publish que gravou. Tags inválidas não são checadas — o deploy não escreve `apiTags`.

Revisão sem `workflowId`/`workflowStageId`, ou stage inexistente no workflow, degrada como no
publish: aviso em `warnings[]` e nenhum bloqueio.

**Onde mora.** O `GovernancePrecheckService.avaliar` já lê o workflow e encontra o stage, mas só
devolve o cálculo dos atributos. Ele passa a expor também o stage encontrado no
`PrecheckResultado`, e o `DeployService` aplica sobre esse stage os dois critérios novos — ambiente
permitido e completeness mínima, que nenhum código lê hoje. O workflow é lido uma vez por execução.
A chamada e o resultado que o `validate` e o `publish` usam não mudam, e as suítes dos dois são a
rede de segurança. As `tags_invalidas` do resultado são ignoradas pelo deploy.

**Alternativa descartada:** um serviço de gate próprio do deploy que lê o workflow por conta própria
e chama o `avaliar` só para os atributos. Mais isolado, mas lê o mesmo workflow duas vezes e
duplica a busca do stage.

### 7. Escrita única

`POST /deployments` com `{environmentId, revisionId, status: "DEPLOYED"}`. O `status` é ignorado
pela plataforma (U-1), mas vai no corpo como a UI envia. Sempre emitido, mesmo com a revisão já no
ar: com revisões fixas, o publish muda o conteúdo da revisão que já está no ambiente, e o novo deploy
é o que leva esse conteúdo ao gateway (E-1).

Recusas: 400 de variável ausente no ambiente e 404 de ambiente inexistente encerram com `exit 1`,
repassando a `message` da plataforma — a de variável ausente é a falha real mais provável ao
promover para HML/PRD. 5xx e falha de rede: `exit 1`, sem retry longo (o adapter já faz 3 tentativas
curtas).

### 8. Falha do deploy ainda produz relatório

O memory bank define falha de deploy como INFO, "para permitir o relatório". Erros **antes** da
escrita (E0–E3) seguem a regra dos outros comandos: só a mensagem e o exit code. Recusa do `POST` ou
divergência na conferência produzem o documento completo com `deployment.status = "FAILED"` e
`exit 1`, para a esteira registrar o que aconteceu.

### 9. Port

`ManagerApiPort.deploy_revision(environment_id, revision_id) -> int` devolve o id do registro de
deploy. É o único método novo; os demais (`get_api_by_id`, `get_workflow`, `list_attributes`,
`get_revision_completeness`) já existem.

### 10. Contrato `apiops.sen-deploy/v1`

```
schema, generatedAt, executionMode,
api          { managerId, name, version, basePath },
revision     { managerId, revisionNumber },
environment  { managerId, name },
governance   { workflowId, stageId, deployableEnvironments[],
               completeness { required, actual }, required[], missing[], violations[], blocked },
previousState { deploymentId, revisionId, revisionNumber, deployedAt } | null,
newState      { deploymentId, revisionId, revisionNumber, deployedAt } | null,
deployment   { attempted, accepted, deploymentId, verified, status: SUCCESS | FAILED, reason },
warnings[]
```

Alimenta o bloco `deployment` do relatório de CD (`artifacts/schemas/cd-report.schema.json`), que é
montado pela esteira. Nunca contém token, variáveis de ambiente nem dump cru do wire.

## Risks / Trade-offs

- **[Conteúdo novo no gateway não provado]** → a E-1 prova que o novo deploy é aceito e registrado,
  não que o gateway passa a servir o conteúdo que o publish acabou de gravar. Prova na verificação
  de ponta a ponta (tarefa 5.3).
- **[Gate duplicado com o AG]** → se a plataforma passar a aplicar o gate no `POST`, o CLI bloqueia
  antes e o resultado é o mesmo. O 412 continua mapeado para `exit 3`.
- **[Corrida entre leitura e escrita]** → um deploy humano entre o E2 e o E4 torna o estado anterior
  impreciso. Aceito: "um deploy por API por ambiente" é garantido pela concurrency da esteira.
- **[Registro sem undeploy]** → o histórico de `deployments` cresce a cada deploy; é o comportamento
  da plataforma.

## Open Questions

Nenhuma para o fluxo normal. Rollback fica com a arquitetura (Non-Goals).
