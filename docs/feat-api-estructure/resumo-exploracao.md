# Resumo do refinamento da estrutura de API

**Atualizado em:** 2026-09-29  
**Escopo atual:** auditoria do objetivo original, identidade/basic info, interceptors e rotas com flows diferentes; fechamento do layout pela D-003.  
**Estado:** layout fechado (D-003); restos de D-002 estacionados; implementação não realizada.

## Objetivo geral

Definir o layout final de uma API consumida pelo APIOps Orchestrator, usando como fontes:

- `arquitetura-apiops-memory-bank/`;
- `mapeamento APIM/`;
- `apiestructure/`;
- `api-gateway/`;
- implementação atual do CLI.

O inventário completo das fontes usadas e o grau de autoridade de cada uma está em [fontes-e-evidencias.md](fontes-e-evidencias.md). Os achados já realizados sobre interceptors, herança e rotas estão em [interceptors-e-rotas-levantamento.md](interceptors-e-rotas-levantamento.md).

## Auditoria de cobertura

Antes desta consolidação, identidade/basic info e os ensaios da API 405 estavam documentados, mas os achados de interceptors e do exemplo `api-gateway` apareciam apenas como próximos passos. Agora todo o levantamento feito até aqui possui registro; isso não significa que todos os temas estejam decididos.

| Objetivo | O que já foi levantado | O que ainda falta decidir |
|---|---|---|
| Layout final | Fechado em [D-003](d003-layout-repo.md): árvore canônica aprovada em 2026-09-29 | Nada estrutural; restos estacionados na seção 8 da D-003 |
| Interceptor | Fechado em D-003: shape declarativo, ordenação por lista, content tipado, custom por ID | Portabilidade cross-tenant de Custom (planejada para depois) |
| Basic info | Binding removido; campos classificados; hidratação validada (API 405); semântica de apiTags, escalares, `tags[]` e `identityApi` fechadas em 2026-09-29 ([varredura 110 APIs](evidencia-tags-e-atributos.md)) | Separação do Adaptive Governance (pendente de produto); replanta de `attributeName` via PUT como validação opcional |
| Rotas com flows distintos | D-003 + **D-005 §6**: `inherit` declarado sempre; herança por escopo | Gramática do tombstone (V-25); governança de valores |

## Decisões já fechadas

### Identidade e binding

- `bindings.json` será removido.
- `spec.id` ficará em `api-basic-info.yaml` e será somente leitura.
- Tenant não será gravado; o token define o tenant.
- Provider não será gravado; o orquestrador suporta somente Sensedia.
- `name` e `basePath` não serão duplicados.
- `lastSynced`, `doNotEdit`, `managedBy` e `$schema` do binding serão removidos.

### Campos declarativos escolhidos até agora

- Manter: `id`, `name`, `version`, `basePath`, `description`.
- Manter: `apiResponsible.username` e `apiResponsible.groupName`.
- Manter: `apiTags[].attributeName` e `apiTags[].tags[]`.
- Suprimir: `tags[]` simples (0/110 APIs com uso) e `identityApi` (decisão do responsável, 2026-09-29).
- Não manter no YAML: visibility, configuração de portal, IDs internos, planos, ambientes, revisões, datas operacionais e contadores.

### Separação fundamental

O YAML não é uma reprodução do objeto do Manager:

```text
manifesto versionado + estado remoto → payload efetivo
```

- O manifesto contém somente dados pertencentes ao usuário/repositório.
- Campos técnicos obrigatórios são obtidos pelo GET remoto no publish.
- Campos preservados automaticamente pelo Manager devem ser omitidos, em vez de receber defaults locais.

## Evidência empírica da API 405

Foi criada a revisão 3, ID 9089, sem deploy. Cada omissão foi testada por PUT e seguida de restauração.

| Comportamento | Campos |
|---|---|
| Omissão retorna HTTP 400 | `visibility`, `apiType`, `creationDate` |
| Omissão apaga o valor | `apiTags` |
| Omissão preserva o valor | `apiSwaggerConfiguration`, `plans`, `environments`, `revisions`, `lastRevision`, `identityApi`, `privateAPI`, `lastVersion`, `appsCount` |
| Resultado ainda limitado | `tags`: testado somente com lista originalmente vazia; varredura de 2026-09-29 (110 APIs) mostrou 0 casos com lista não-vazia, inviabilizando o cenário em produção ([evidência](evidencia-tags-e-atributos.md)) |

Também foi comprovado que:

- `visibility` reduzida remove `users[]`;
- defaults falsos de portal alteram `showAppRegister` e `privateAPI`;
- `apiResponsible` sem ID é resolvido pelo username;
- IDs internos podem ser regenerados durante writes e não são identidades versionáveis;
- `environments: []` não apagou os ambientes;
- revisões reduzidas foram aceitas, mas podem ser simplesmente omitidas.

## Payload mínimo de basic info proposto

```text
Do YAML:
  id, name, version, basePath, description,
  apiResponsible.username/groupName,
  apiTags

Do GET remoto:
  visibility completo,
  apiType,
  creationDate

Omitir do payload:
  tags, identityApi,
  apiSwaggerConfiguration, plans, environments,
  revisions, lastRevision, flags e contadores preservados pelo Manager
```

## Aplicação da D-003 (2026-09-29)

As perguntas abaixo foram trabalhadas no grill de definição do layout e na reunião "[APIOps] Dúvidas Estrutura" (2026-09-28). O resultado consolidado está em [D-003](d003-layout-repo.md); os status inline refletem essa atualização.

## Perguntas do grill-me ainda sem resposta do responsável

Estas perguntas exigem decisão de produto; os testes técnicos não as substituem.

1. **`identityApi`:** — **RESOLVIDA (responsável, 2026-09-29).** `Manter? Não`: não versionar e não enviar; omissão aceita e preservada (API 405); 0/110 APIs com `true`.
2. **`apiTags[].attributeName`:** — **RESOLVIDA (refinamento 2026-09-29, [evidência](evidencia-tags-e-atributos.md)).** O YAML é lista declarativa completa: editar `tags[]` redefine valores; alterar `attributeName` replanta o par via PUT (tecnicamente viável, comprovado que o PUT da revision muta os bindings), desde que o nome exista no catálogo de Attributes do AG. Criação de atributos/valores novos permanece no produto AG.
3. **Ausência de `apiTags`:** — **RESOLVIDA (D-003 §3).** Ausência no YAML preserva as tags remotas; `apiTags: []` representa remoção explícita.
4. **`tags[]` simples:** — **RESOLVIDA/SUPRIMIDA (2026-09-29).** Varredura de 110 APIs: zero usos; omissão preserva. Fora do YAML e do payload.
5. **Shape final:** — **RESOLVIDA (D-003 §3).** `spec.<campo>` direto confirmado.
6. **`apiResponsible.groupName`:** — **RESOLVIDA com regime diferente (D-003 §3).** Presente no YAML, hidratado no import, read-only no MVP (sem atualização via CLI neste momento).
7. **Campos opcionais:** — **RESOLVIDA (D-003 §3, refinamento 2026-09-29).** Listas: ausente preserva, `[]` remove. Escalares: ausente preserva, `""` limpa, `null` proibido no schema.
8. **Adaptive Governance:** — **PENDENTE (produto).** Confirmar se `apiTags` pertence definitivamente ao `api-basic-info.yaml` — o contrato atual pressupõe que sim (nenhum manifesto separado existe no layout).
9. **Campos somente leitura:** — **ESTACIONADA.** Fluxo administrativo para mudar `id`, `basePath` ou responsável permanece pendente.

### Interceptors, resources e rotas

10. **Forma do flow:** — **RESOLVIDA (D-003 §4).** Cada nível que declara, declara o flow efetivo completo; sem merge de deltas.
11. **Herança:** — **RESOLVIDA (D-003 §1/§4).** Busca ascendente por pasta; nearest-parent vence.
12. **Remoção:** — **REABERTA (D-005 / V-25).** `inherit: false` sinaliza a quebra, mas a gramática da remoção seletiva continua sem definição; o caso é real nas APIs 409 e 417.
13. **Reuso:** — **RESOLVIDA (D-003 §1).** Template canônico no Manager (Golden Path); o repo apenas referencia `spec.template`.
14. **Arquivos de flow:** — **ATUALIZADA (D-005 §3/§4).** Revisions seguem fora do repo; o escopo `all` tem arquivo próprio e `resource.yaml` deixou de ser mapa leve.
15. **Índice:** — **RESOLVIDA (D-003 §2 + D-005 §4).** Descoberta recursiva por `resources/<slug>/`; sem `resources.yaml`.
16. **Granularidade:** — **CONFIRMADA.** Exatamente uma operation por arquivo.
17. **Nome de arquivo:** — **RESOLVIDA (D-003 §2).** `{metodo}_{parametros}.yaml` com path params entre chaves; colisão é erro de validação.
18. **Ordenação:** — **RESOLVIDA (D-003 §4).** Ordem da lista é a fonte; position calculada só no payload.
19. **Execution point:** — **RESOLVIDA (D-003 §1/§4).** Tags `interceptors_request`/`interceptors_response`; FIRST/SECOND é interno do CLI.
20. **Status:** — **RESOLVIDA (D-003 §4).** Fora do YAML.
21. **Content:** — **RESOLVIDA (D-003 §4).** Objeto YAML tipado; serialização para string JSON apenas no adapter.
22. **Custom:** — **PARCIAL.** ID numérico por ora (D-003 §4); portabilidade cross-tenant e versionamento do script seguem estacionados.
23. **Precedência:** — **PARCIAL.** Destination ausente/branco herda nativamente do fluxo geral; validação de destination por rota e precedência fina de timeout ficam para o refinamento do validador.
24. **Revision:** — **SUPRIMIDA.** Sem pastas de revision no repo; a esteira indica a revision-alvo (uma por ambiente).
25. **OpenAPI:** — **ADIADA por decisão.** OpenAPI não versionado neste momento; methods/paths vêm dos arquivos de operation.
26. **Importação:** — **ATUALIZADA (D-005 §8).** A heurística compara com o fluxo da **própria revision**, inclui `content`, usa sequência e particiona governado × não governado; item governado não representável ⇒ falha explícita.

A descrição e as validações técnicas correspondentes estão detalhadas em [interceptors-e-rotas-levantamento.md](interceptors-e-rotas-levantamento.md). As decisões que responderam estas perguntas estão consolidadas em [d003-layout-repo.md](d003-layout-repo.md).

## Pendências técnicas para fechar D-002

- Atualizar o schema para o shape e obrigatoriedade aprovados.
- Manter `spec.id` na importação; parar de removê-lo.
- Deixar de injetar `Settings.API_ID` como fonte da identidade.
- Ler `apiTags` do manifesto, não de `API_TAGS_*` como fonte prioritária.
- Hidratar `visibility` integral, `apiType` e `creationDate` pelo GET.
- Remover defaults destrutivos de `apiSwaggerConfiguration`.
- Não serializar `environments: []` nem histórico reduzido sem necessidade.
- Implementar semântica explícita de ausência versus lista vazia para tags.
- Criar testes de regressão usando o baseline da API 405.
- Atualizar templates, exemplos e documentação ativa; remover `bindings.json`.

## Validações ainda não realizadas

- ~~Omissão de `tags` quando a lista remota contém valores.~~ Inviável em produção: varredura de 110 APIs (2026-09-29) encontrou 0 casos não-vazios; a decisão tomada (suprimir) independe, pois a omissão já provou preservar ([evidência](evidencia-tags-e-atributos.md)).
- Comportamento de `identityApi: true`, pois nenhuma API encontrada usa esse valor.
- Isolamento leave-one-out dos campos do envelope raiz da revisão; o envelope denso funcionou, mas cada campo raiz não foi removido individualmente.
- Execução do CLI corrigido de ponta a ponta; os testes foram feitos diretamente na Manager API.
- Matriz controlada de herança revision → resource → operation.
- Remoção/tombstone nos níveis de resource e operation.
- Unidade real de ordenação de `position` por escopo e `executionPoint`.
- Round-trip portável de Custom interceptor sem ID fixo de tenant.
- Omissão isolada dos campos operacionais de interceptor (`parent`, `idTemp`, `persist`, `isBroken`).
- Publicação de duas operations do mesmo resource com flows diferentes usando o CLI.

## Estado externo aguardando decisão

- API 405 está com revisão 3, ID 9089, como última revisão, sem deploy.
- Revisão 2 continua implantada no Default.
- O reset da API 405 será feito somente quando solicitado.
- A credencial exposta na sessão deve ser rotacionada quando o usuário indicar.

## Próximos refinamentos

1. Fechar as pendências restantes de D-002/D-003 (separação do Adaptive Governance; fluxo admin de `id`/`basePath`/responsável).
2. Especificar a esteira de publish/revision (alvo por ambiente) e o mecanismo de validação contra o template do Manager.
3. ~~Planejar a portabilidade de Custom interceptors (referência por nome/alias)~~ — **decidido em
   2026-10-15:** permanece o `id` numérico, estável dentro de um ambiente; a validação na troca é do
   dev, e o aborto por `Custom` inexistente a torna visível. Segue aberto o versionamento de scripts.
4. Detalhar validação de destination por rota e de valores do template (rate limit etc.).
5. Criar a proposal de implementação a partir da fila de impactos da [D-003](d003-layout-repo.md#9-impactos-de-implementação-fila-de-proposta).
6. Só então alinhar importer, models, schemas, exportador e publicador ao contrato aprovado.
