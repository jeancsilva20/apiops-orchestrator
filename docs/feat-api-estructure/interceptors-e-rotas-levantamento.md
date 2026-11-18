# Levantamento — interceptors, escopos e rotas com flows diferentes

> ⚠️ **Registro histórico.** Alinhado à [D-005](d005-layout-revisado.md) em 2026-10-14: as respostas abaixo refletem o estado da discussão na época. Onde a D-005 revisou, vale a D-005.


**Status:** evidências consolidadas; contrato fechado em [D-003](d003-layout-repo.md) (2026-09-29).  
**Atualizado em:** 2026-09-29.

> **Nota de fechamento:** as decisões de contrato que este levantamento deixava em aberto foram feitas na reunião "[APIOps] Dúvidas Estrutura" (2026-09-28) e no grill de layout (2026-09-29), consolidadas na D-003. As seções 5 e 6 abaixo permanecem como registro histórico das restrições e questões; os status resolvidos constam no [resumo](resumo-exploracao.md).

## Perguntas investigadas

1. Como um interceptor é representado pelo Manager e pelos layouts candidatos?
2. Em quais níveis um flow pode existir?
3. Como representar duas rotas com flows diferentes?
4. O que o CLI atual já suporta e o que ele perde?

## 1. Shape observado no Manager

O shape base observado é:

```yaml
position: 0
type: OAuth
group: Security
content: '{"grantTypes":["CLIENT_CREDENTIALS"]}'
executionPoint: FIRST
status: REFERENCE
idTemp: 1
persist: true
isBroken: false
```

Constatações:

- `content` chega no wire como string JSON para interceptors configuráveis;
- o conteúdo varia por `type`;
- custom interceptors retornam dados como `id`, `name`, `script`, `abort`, `debug` e `tags`, além da referência `customInterceptorId` em shapes observados;
- `executionPoint` separa etapas como `FIRST` e `SECOND`;
- `status: REFERENCE` representa uma entrada ativa/referenciada;
- `status: REMOVED`, junto de uma referência ao `parent`, foi observado em resource para suprimir um interceptor herdado da revision;
- `id`, `idTemp`, `persist`, `isBroken`, `parent` e IDs internos são detalhes do Manager até que se prove necessário versioná-los.

### Posição não é identidade global

Nos payloads observados, `position` deve ser interpretado dentro do contexto do flow/escopo e do execution point. Há início em zero, repetição entre execution points e lacunas. Logo, a renumeração global feita hoje por `ApiFull.set_interceptor_positions()` não representa com fidelidade a semântica do Manager.

Ainda está aberto se o YAML final manterá `position` explícita ou se a ordem da lista será a fonte declarativa e a posição será calculada somente no payload.

## 2. Escopos existentes

As evidências mostram três níveis:

```text
revision
└── resource
    └── operation (método + path)
```

- **Revision:** políticas comuns a toda a revision.
- **Resource:** políticas comuns às operations agrupadas naquele resource e alterações da herança da revision.
- **Operation:** comportamento específico de uma rota.

A API 400 fornece um caso real de herança/supressão: o OAuth do flow da revision aparece como `REMOVED` nos resources `Token` e `Groups`, evitando que as rotas de bootstrap exijam um Bearer anterior.

Isto comprova a necessidade de representar mais do que uma lista plana global. Ainda não comprova qual deve ser a sintaxe declarativa do merge.

## 3. O que os exemplos propõem

### `apiestructure`

O candidato contém:

```text
revisions/{n}/revision-flow.yaml
revisions/{n}/resources/{resource}/resource.yaml
revisions/{n}/resources/{resource}/operations/{method}_{path}.yaml
```

Há listas de interceptors nos três níveis. Porém, os mesmos flows são repetidos integralmente em revision, resource e operation. O exemplo não informa se a lista de um nível:

- substitui o parent;
- acrescenta itens ao parent;
- representa o flow efetivo já expandido;
- precisa de tombstones para remover itens herdados.

Também usa `content: <id numérico>` para `Custom`, o que acopla o arquivo ao catálogo do tenant.

### `api-gateway`

O exemplo usa:

- `Resources/resources.yaml` como índice de resources e operations;
- um arquivo separado por operation;
- uma lista completa de interceptors dentro de cada operation;
- `Templates/default-interceptors.yaml` como flow padrão, sem referência formal entre o template e as operations.

Nos 26 arquivos de operation foram encontrados 23 flows distintos. O prefixo `Service callout` + `Custom 241` é recorrente, mas o callout e o custom seguinte variam por rota. Este exemplo demonstra por que cada rota precisa poder declarar uma diferença, mas também evidencia o custo de duplicar flows completos.

## 4. Estado do CLI atual

| Capacidade | Estado atual |
|---|---|
| Flow de revision | Lido de `revision-flow.yaml`. |
| Flow de operation | Lido do arquivo individual da operation. |
| Flow de resource | Está previsto no schema, mas é descartado pelo importer/model final. |
| `destination` e `timeout` de resource | Estão previstos no exemplo/schema, mas são descartados. |
| Custom interceptor | YAML usa ID numérico; conversor busca o custom no Manager e serializa o objeto retornado. |
| Posições | O model renumera globalmente revision + todas as operations. |
| `REMOVED`/parent | O exportador remove `parent`; não há algoritmo explícito de herança/supressão. |
| Vários itens em um arquivo de operation | O parser sobrescreve a entrada por `fileName`; na prática, preserva somente a última operation do arquivo. |

Consequência: o CLI atual não consegue fazer round-trip fiel de uma API que use flows em resource ou tombstones de herança.

## 5. Baseline de desenho para a próxima decisão

Os achados sustentam estas restrições mínimas (parcialmente supersede — item 1 e índice — pelas decisões da D-003):

1. ~~Deve existir um lugar explícito para flow de revision, resource e operation.~~ **D-005 §3/§4:** os três escopos têm flow — o `all` ganhou arquivo próprio e o `resource.yaml` deixou de ser mapa leve.
2. A chave natural de uma rota é `method + path`; o arquivo individual de operation é um bom limite de edição para flows diferentes. **Confirmado na D-003.**
3. Um flow comum não deve precisar ser copiado para todas as operations apenas para produzir o payload efetivo. **Resolvido via template canônico + herança ascendente + append.**
4. O layout precisa expressar remoção de um interceptor herdado. **Reaberto (D-005 / V-25):** `inherit: false` sinaliza, mas a gramática da remoção seletiva segue sem definição.
5. IDs internos e posições do Manager não devem ser confundidos com identidade declarativa estável. **Confirmado na D-003.**
6. Custom interceptors precisam de uma referência portável entre tenants ou de uma regra explícita de resolução. **Por ora ID numérico; portabilidade estacionada.**
7. O conversor deve calcular o payload efetivo sem destruir informações de resource/operation. **Confirmado; destino do cálculo descrito em D-003 §6.**

## 6. Questões (registro histórico — respostas em D-003 e no resumo)

Todas as questões abaixo foram respondidas, adiadas ou estacionadas conforme anotado no [resumo-exploracao](resumo-exploracao.md). Mantidas aqui para rastreabilidade das alternativas consideradas.

### Modelo de herança

1. Cada nível declara somente seu delta ou o flow efetivo completo? → **Flow completo quando declara; herança por busca ascendente (D-003).**
2. A operation herda automaticamente `revision + resource`? → **Sim, até o template canônico; sem pastas de revision no repo (D-003).**
3. Se houver herança, como o usuário remove um item herdado? → **em aberto (V-25)**; `inherit: false` marca a quebra (D-005 §6).
4. O repositório deve preservar tombstones vindos do Manager? → **em aberto (V-25)**; hoje o import marca `inherit: false` e registra o item removido em comentário.

### Organização dos arquivos

5. Manter `revision-flow.yaml` e `resource.yaml` com interceptors, ou centralizar flows em arquivos reutilizáveis? → **Nem um nem outro: template canônico no Manager (D-003).**
6. Permitir templates/composição para o prefixo comum? → **D-005 §3**: herança por escopo, com substituição; a régua (API 414) valida, não compõe.
7. `resources.yaml` continuará sendo um índice ou a árvore de diretórios será descoberta sem índice? → **Descoberta recursiva, sem índice (D-003).**
8. Cada arquivo terá exatamente uma operation? → **Sim, confirmado (D-003).**
9. Qual convenção final de nomes tratará método, path params e colisões de paths com o mesmo slug? → **`{metodo}_{parametros}.yaml` com chaves; colisão é erro de validação (D-003).**

### Shape do interceptor

10. A ordem da lista substitui `position` no YAML ou `position` continua obrigatória? → **Ordem da lista vence; position só no payload (D-003).**
11. `executionPoint` permanecerá como enum do Manager (`FIRST`, `SECOND`, `THIRD`) ou terá nomes semânticos convertidos pelo CLI? → **Tags `interceptors_request`/`interceptors_response`; FIRST/SECOND interno (D-003).**
12. `status` deve aparecer no YAML para itens normais ou apenas para exceções como remoção? → **Fora do YAML (D-003).**
13. O `content` será um objeto YAML tipado por interceptor, mesmo que o Manager espere uma string JSON? → **Sim, tipado; string JSON só no adapter (D-003).**
14. Como um custom será identificado de modo estável: ID numérico, nome, alias local ou arquivo próprio? → **ID numérico por ora; portabilidade estacionada (D-003).**
15. O script do custom pertence a este repositório de API ou a um repositório/catálogo separado? → **Estacionado (catálogo do Manager por ora; decidir na esteira de portabilidade).**
16. Quais campos opacos do Manager precisam ser reidratados no publish, se houver? → **Tratados na matriz de hidratação da D-002; opérationais (`parent`, `idTemp`, `persist`, `isBroken`) seguem pendentes de teste.**

### Revisions e fonte da verdade

17. Cada diretório de revision é um snapshot completo e imutável ou pode conter deltas sobre a anterior? → **Suprimida: sem revisions no repo; a esteira aponta a revision-alvo por ambiente (D-003).**
18. OpenAPI ou arquivos de resource/operation definem methods e paths quando houver divergência? → **Arquivos de operation; OpenAPI não versionado neste momento (D-003).**
19. `destination` e `timeout` podem existir nos três níveis? Qual regra de precedência deve ser aplicada? → **Operação declara; ausente/branco herda nativamente do fluxo geral; precedência fina adiada para o validador (D-003).**
20. Ao importar, forma expandida ou canônica? → **Canônica, com diff contra o fluxo da própria revision e `inherit` (D-005 §8).**

## 7. Validações empíricas que ainda faltam

- Montar uma matriz controlada com um interceptor em revision, outro em resource e outro em operation.
- Remover um interceptor herdado em resource e em operation e comparar o wire.
- Alterar positions separadamente em `FIRST` e `SECOND` para confirmar a unidade de ordenação.
- Fazer round-trip de pelo menos um custom sem depender de ID específico do tenant.
- Confirmar o comportamento de dois interceptors iguais no mesmo flow e como distingui-los para remoção.
- Testar se omitir `parent`, `idTemp`, `persist` e `isBroken` em cada escopo é aceito ou exige hidratação.
- Validar no Manager um layout com duas operations do mesmo resource e flows diferentes.
- Executar importação e publicação end-to-end depois que o model de resource preservar seus campos.

## 8. O que já pode ser considerado respondido

- Rotas diferentes precisam de uma unidade própria de configuração: o arquivo de operation atende a isso.
- Interceptors não existem apenas no nível global; revision, resource e operation são escopos relevantes.
- O layout atual do CLI perde dados de resource e não faz round-trip fiel.
- A lista do Manager não deve ser copiada cegamente para YAML: conteúdo deve ser legível, IDs internos devem ser filtrados e campos operacionais precisam de regra de hidratação.
- A decisão que faltava não era se haveria flows diferentes, mas como herança, reuso, remoção e identidade seriam expressos — **respondida na D-003**: herança ascendente, reuso por template canônico, remoção via override total e identidade por arquivo/rota com Custom por ID.