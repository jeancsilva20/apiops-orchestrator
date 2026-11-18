## Design

### Contexto

O `sen validate` e o `sen publish` gravam o repositório na revisão por um único `PUT /revisions/{id}`, montado em `revision_payload.montar` e conferido em `revision_payload.conferir`, pelo `RevisionWriter`. Esse PUT carrega o runtime (interceptors, destinos, recursos, rotas) e o basic info no `api` aninhado. O contrato OpenAPI sobrevive a ele, mas ele não o escreve.

O caminho que escreve o contrato é `GET`/`PUT /revisions/{id}/swagger` (OpenAPI 3.0 com extensões `x-*`). Medido na API-lab 425:

| Fato | Fonte |
|---|---|
| O PUT reescreve a revisão inteira e recria todos os interceptors com ids novos; a semântica é preservada quando os `x-*` voltam | V-28 §7 |
| Swagger sem `x-interceptors` apaga todos os interceptors com `success`; sem extensões, cria um recurso por path | V-28 §7 |
| As seções `schemas`, `securitySchemes`, `responses`, `requestBodies`, `headers`, `examples` são mantidas, e os `$ref` para elas também | I-8, I-8b |
| O `$ref` de **parâmetro** na operação é expandido pelo Manager | I-8 |
| O Manager explicita `style`, `explode` e `required: false` em parâmetros e headers, e reordena o `required` dos schemas | I-8 |
| `x-*` voltam iguais; runtime, workflow, stage, `apiTags`, responsável, descrições e destinos não mudam | I-8 |
| `security`/`securitySchemes` não criam interceptor; `tags` de operação não movem a rota de recurso | I-8 |
| Rota nunca documentada fica com `parameters: []` e `responses: {'200': {description: OK}}` | backup da 425, rev 2 |
| `servers` vem relativo (`/<basePath>`) na 425; em outras APIs, absoluto | backup da 425, rev 2; I-6 |
| Interceptor `THIRD` presente no documento atravessa o PUT de swagger igual (tipo, posição, status, script); swagger **sem** ele o apaga | I-2 (Draft da 425, restaurada) |
| O GET do swagger vem sempre em JSON; 11 de 40 APIs do consulting estão em **Swagger 2.0**; as demais em 3.0.0, 3.0.3 ou 3.0.4; nenhuma usa `$ref` de parâmetro nem `ANY` | I-6 |
| O completeness avalia o contrato (tamanho de `summary` e das `description` de respostas, parâmetros, schemas e propriedades): contrato pouco descrito **baixa** a nota (97 → 89,5 na Draft da 425) | I-7 |

Mapa de cenários, decisões numeradas e resultados das medições: [`cenarios-de-teste.md`](../../../docs/feat-contrato-openapi/cenarios-de-teste.md). A série de quatro documentos da APIOPS-115 (G1–G13) está nos anexos da task; as divergências deste desenho em relação a ela estão na D14.

### Decisões

**D1 — Onde roda.** O contrato é uma **etapa** do `sen validate` e do `sen publish`, não um comando. As validações locais ficam num serviço isolado (Swagger validate) que não depende de rede nem dos comandos, para que um comando futuro possa expô-lo ao dev.

**D2 — Fluxo.** As etapas novas estão em negrito; as demais são as de hoje.

| # | Etapa | Rede | Desfecho de erro |
|---|---|---|---|
| E1 | carregar o repositório, `components.yaml` incluso | — | exit 1 |
| **C0** | **Swagger validate: validações (D6) e normalizações (D7)** | — | **exit 1, nada gravado** |
| E2 | API, guarda de identidade, régua, Custom, montagem do fluxo | GET | como hoje |
| — | pré-check de governança | GET | como hoje (exit 3) |
| **C1** | **GET do swagger; detecta 2.0; calcula o que some da documentação (D11)** | GET | **warning; a etapa de contrato não roda** |
| — | confirmação (só `validate` local), com os avisos do fluxo e do contrato | — | exit 130 |
| E3 | PUT da revisão | PUT | como hoje |
| E3.1 | conferência do fluxo | GET | como hoje (exit 1) |
| **C2** | **GET do swagger; alinhamento ao fluxo da E3.1 (D16); montagem (D3–D5); sem mudança → fim (D9)** | GET | **warning** |
| **C3** | **PUT do swagger** | PUT | **warning; fluxo mantido** |
| **C4** | **conferência nova (D10)** | GET ×2 | **warning; fluxo mantido** |
| E4 | completeness (só `validate`) | GET | como hoje |

C1 lê o swagger antes da escrita só para avisar; o documento que vai no PUT é montado em C2, sobre um GET posterior à E3, porque os `x-*` mudam com a gravação da revisão.

**D3 — Fonte de cada campo no documento gravado.**

| Campo | Fonte | Ausente no repo |
|---|---|---|
| `openapi`, `servers`, `info.title`, `info.version`, `info.description` | GET | — |
| `info.contact` | `api-basic-info.yaml` → `spec.contact` | removido |
| `tags` (raiz) | `api-basic-info.yaml` → `spec.tags` | removido |
| `security` (raiz) | `api-basic-info.yaml` → `spec.security`; `[]` vale como ausente, porque o Manager o guarda como `null` (medido em 2026-10-28; o `[]` de operação é mantido) | removido |
| `components.schemas`, `securitySchemes`, `responses`, `requestBodies`, `headers`, `examples` | `components.yaml`, seção inteira | seção removida |
| `components.parameters`, `links`, `callbacks` e outras seções | GET | — |
| `paths.<p>.parameters` (path item) | — | removido (os do recurso entram na operação, D5) |
| operação: `operationId`, `tags`, `requestBody`, `security` | arquivo da operação | removido |
| operação: `parameters` | `resource.yaml` + arquivo da operação (D5) | `[]` |
| operação: `responses` | arquivo da operação | **erro de validação** (D4) |
| operação: `summary` | arquivo da operação | a `description` da operação |
| operação: `description` e demais chaves fora do modelo | GET (a `description`, do fluxo da E3.1 quando o GET diverge dele, D16) | — |
| operação que o repositório não tem | — | removida, e o path que fica sem operação também (D15) |
| `x-*` em qualquer nível | GET, intactos; quando o GET diverge do fluxo da E3.1, os da raiz, de `x-resources` e das operações vêm do fluxo (D16) | — |

As rotas do documento são as do fluxo que a E3 gravou e a E3.1 conferiu. Se o GET de C2 não as descreve — rota a menos ou a mais, interceptor, destino ou descrição diferentes —, o documento é alinhado ao fluxo antes da montagem (D16). Operação que o repositório não tem sai do documento (D15).

**D4 — `responses` é obrigatório; "em branco" é o estado de rota não documentada.** O estado que o Manager dá a uma rota nunca documentada é `parameters: []` e `responses: {'200': {description: OK}}`, e é assim que o importador puxa essa rota. Na subida, `responses` ausente no arquivo da operação significa que alguém apagou: é **erro de validação** (D6, checagem 16), sempre. `parameters` ausente vale como `[]`. Consequência de rollout: a versão do orquestrador só vai para uso depois que todos os repositórios forem puxados de novo com o importador ajustado — antes disso, nenhum tem `responses`.

**D5 — Parâmetros.** Escritos por extenso — `components.parameters` não entra no modelo, porque o Manager expande o `$ref` de parâmetro (I-8). Os do `resource.yaml` são copiados para **cada operação** do recurso, e não para o path item: um mesmo path pode ter métodos em recursos diferentes, e o path item seria disputado. Mesmo `name`+`in` no recurso e na operação: a operação sobrescreve. Parâmetro de path no `resource.yaml` precisa existir no template de todas as rotas do recurso; o que não é de todas vai no arquivo da rota. Na gravação, cada parâmetro leva os `x-*` do parâmetro do swagger atual com o mesmo `name`+`in` (da operação ou, na falta, do path item), sem sobrescrever o que o repositório declara (C6, decisão do usuário em 2026-10-26): o repositório não aceita `x-*`, e sem isso o `x-example` que o Manager guarda nos parâmetros se perdia a cada gravação (visto na rev 1 da 426).

**D6 — Validações do Swagger validate.** Todas rodam sem rede, antes de qualquer escrita; erro → exit 1, citando arquivo e posição.

| # | Checagem |
|---|---|
| 1 | Campo fora do modelo: `x-*` em qualquer YAML; `servers`/`info` no basic info; `parameters`/`links`/`callbacks` ou seção desconhecida no `components.yaml`; `components.yml` na raiz |
| 2 | `$ref` existe no `components.yaml` |
| 3 | `$ref` é da seção que a posição pede (`responses.<status>` → `responses`; `requestBody` → `requestBodies`; `schema` → `schemas`; `headers.<nome>` → `headers`; `examples.<nome>` → `examples`) |
| 4 | `$ref` só interno (`#/components/...`); arquivo, URL ou `#/definitions/` é erro |
| 5 | Ciclo de `$ref` fora de `schemas` |
| 6 | `security` (raiz e operação) só cita esquemas de `securitySchemes` |
| 7 | Parâmetro de path do `resource.yaml` existe no template de todas as rotas do recurso |
| 8 | Cada `{param}` da rota tem parâmetro `in: path` (recurso ou operação), e todo `in: path` da operação existe no template |
| 9 | Parâmetro de path tem `required: true` |
| 10 | `name`+`in` repetido no mesmo arquivo |
| 11 | `operationId` único na API |
| 12 | `requestBody` só em POST, PUT e PATCH |
| 13 | Toda resposta tem `description`; status de três dígitos, `1XX`–`5XX` ou `default` |
| 14 | `example`/`examples` e `default` compatíveis com o schema: tipo, `enum`, `format` básico (`date`, `date-time`, `uuid`, `int32`, `int64`) |
| 15 | `enum` coerente com o `type` |
| 16 | Toda operação declara `responses` (D4) |

**Avisos (não bloqueiam).** Descrição abaixo do mínimo que o completeness cobra (I-7) vira warning, para o dev ver antes de a nota cair: `summary` e `description` de resposta com mais de 4 caracteres; `description` da rota com mais de 9 (vazia também conta: medido na Draft da 425 em 2026-10-27, "description \"\" is too short"); `description` de parâmetro com mais de 4; de propriedade com pelo menos 9; de schema com mais de 9; schema de objeto sem propriedades. A mensagem agrupa por regra, só as que aparecem, com o mínimo de caracteres e o tamanho de cada item; `summary` tirado da `description` é marcado e explicado. Os mínimos vêm das mensagens do Manager e podem mudar com ele. Schema sem a chave `properties` vira um aviso próprio (I-9: o completeness acusa `string` com ou sem `enum`, `object` sem `properties`, `array`, `allOf` e mapa; não acusa `properties: {}`), agrupado pelo que o schema é: tipo simples ou lista → declarar direto na propriedade que o usa, no lugar do `$ref`, e apagar o schema; objeto → declarar as propriedades; composição ou mapa → acrescentar `properties: {}`, que não muda o contrato.

Sem validador OpenAPI genérico nesta change: acusaria também o que vem do Manager e é dependência a mais no executável.

**D7 — Normalizações** (não são erro): status numérico (`200:`) vira string; data implícita do YAML (`2024-01-01`) vira string ISO; `summary` ausente recebe a `description`.

**D8 — Problema da plataforma não derruba o fluxo.** Swagger 2.0 no GET, GET ou PUT recusado, 5xx que persiste depois dos retries do `HttpClient`, swagger que não pode ser alinhado ao fluxo (D16) e conferência divergente viram **warning**: em `achados` no `validate`, em `avisos` no `publish`. Exit 0. O fluxo gravado e conferido na E3/E3.1 fica. **Sem rollback.** O `-o` dos dois comandos ganha `documentation: {status, reason}` (decisão do usuário em 2026-10-26): `status` é `updated` (a documentação mudou nesta execução: pelo PUT do swagger ou já pelo PUT da revisão, como `description` de rota ou rota nova; também quando a conferência diverge ou a releitura falha, com o motivo), `unchanged` (a documentação lida em C1, antes de qualquer gravação, é a mesma de C2, sem contar `x-interceptors`, `x-destination` e `x-timeout`) ou `not_updated` (2.0, leitura, recusa, falha ou swagger que não pode ser alinhado, com o motivo). Quando C2 alinhou o swagger ao fluxo (D16), o `-o` ganha `documentation.aligned` com o que foi alinhado; sem alinhamento, o campo não aparece, e o texto não menciona o alinhamento (decisão do usuário em 2026-10-28). O motivo também segue nos warnings, e o texto ganha a linha "Documentação atualizada: sim / não / sem mudança", com o motivo logo abaixo, fora do bloco "O que vai mudar no Manager". (2026-10-27: comparar só C2 dava "sem mudança" quando o PUT da revisão já tinha levado a `description` nova da rota.)

**D9 — Sem mudança, sem PUT.** O documento montado em C2 é comparado, normalizado (D10), com o GET de C2. Igual → não há PUT, e os interceptors não são recriados à toa.

**D10 — Conferência nova (C4).** Compara o documento **normalizado**: padrões do OpenAPI aplicados (`style`, `explode`, `required: false`), `required` dos schemas como conjunto, `$ref` resolvidos. Três partes:

1. o contrato do repositório está no swagger como declarado;
2. os `x-*` são estruturalmente iguais aos do documento enviado (não byte a byte; ids e chaves locais não contam);
3. o runtime da revisão é o que a E3.1 aprovou: `revision_payload.conferir(estado da E3.1, GET da revisão)`, mais `workflowId` e `workflowStageId`. Para isso o `RevisionWriter.gravar_e_conferir` passa a devolver o estado lido na E3.1.

**D11 — Aviso do que some.** Em C1, o que o swagger atual tem nos campos governados e o repositório não declara vira aviso: por operação (`responses`, `parameters`, `requestBody`…), por componente e na raiz. Parâmetro do nível do path só entra no aviso, como `GET /x · parâmetro id (path)`, quando uma rota do repositório naquele path não o declara: nas que declaram ele só muda para a operação (D5), e rota que só o Manager tem já sai pela gravação do fluxo, que avisa (corrigido em 2026-10-27; antes todo parâmetro do path era anunciado). No `validate` local o aviso entra na confirmação, junto com "o swagger da revisão também será gravado", e com ele o aviso de descrições abaixo do mínimo do completeness (D6), que já se sabe antes de qualquer chamada; nenhum dos dois se repete no resultado local (decisão do usuário em 2026-10-27). Na esteira, o aviso do que some vai para o `-o`; o de descrições não, porque as sugestões do completeness no `-o` já listam cada descrição curta. Se C1 detectar 2.0, a confirmação diz que o contrato não será gravado e o fluxo será.

**D12 — Itens fora de `FIRST`/`SECOND` vão como vieram.** A I-2 mediu: um `THIRD` presente no documento atravessa o PUT de swagger igual, e um swagger sem ele o apaga. Como o documento parte do GET (D3), o item vai junto nos `x-interceptors`. Nesta fase não há tratamento especial — nem guarda, nem conferência própria (decisão de 2026-10-26: caminho feliz). `ANY` não foi medido; nenhuma das 41 APIs lidas tem.

**D13 — A etapa sempre roda.** Premissa: o repositório é puxado do Manager já com o contrato. Campo governado ausente vai em branco, com o aviso da D11; `responses` ausente é erro (D4).

**D14 — Divergências em relação à série da APIOPS-115.**

| # | Onde no card | O card diz | Este desenho | Por quê |
|---|---|---|---|---|
| 1 | doc 4 §3.2; doc 2 G6 | `components.yaml` só com `schemas` e `securitySchemes` | + `responses`, `requestBodies`, `headers`, `examples`; `parameters` fica fora | padrão OpenAPI; o Manager mantém essas seções e expande o `$ref` de parâmetro (I-8, I-8b) |
| 2 | doc 3 §4, regra 4 | `$ref` sempre para `components.schemas` | `$ref` para a seção que a posição pede, validado | consequência da linha 1 |
| 3 | critério de aceite 2 | `$ref` quebrado falha antes do PUT | vale para todas as seções do modelo e falha antes de **qualquer** escrita, inclusive a da revisão | erro do dev não deixa a revisão pela metade |
| 4 | doc 3 §5.2, regra 3 | sobre o GET entram só os campos faltantes | o repositório é a verdade nos campos que governa: declarado substitui, ausente vai em branco, com aviso | decisão do decisor |
| 5 | doc 2 G11; doc 4 §3.4 | não diz se `responses` é obrigatório | `responses` obrigatório em toda rota; rota não documentada = `'200': OK`, como o importador puxa | evita apagar respostas por engano; o rollout depende do importador |
| 6 | doc 4 §3.1; doc 2 G2 | `servers` no `api-basic-info.yaml` | fora do repositório; vem do GET | `servers` mexe no `basePath`, que é identidade imutável (D-11) |
| 7 | doc 3 §1; doc 4 §4 | `info.title`/`version`/`description` vêm do repositório | vêm do GET | já gravados pelo PUT da revisão; mesmo valor |
| 8 | doc 4 §3.3 | parâmetros de path no `resource.yaml`, no nível do path | no `resource.yaml`, copiados para cada operação do recurso; precisam existir em todas as rotas; a rota sobrescreve | um recurso tem vários paths, e um path pode ter métodos em recursos diferentes |
| 9 | critério de aceite 3 | merge preserva `x-*` byte a byte | igualdade estrutural | o JSON é re-serializado |
| 10 | critério de aceite 4 | PUT grava; GET de conferência valida | conferência do contrato normalizada + conferência do runtime | o Manager acrescenta padrões do OpenAPI e reordena `required` (I-8); o PUT de swagger recria os interceptors |
| 11 | Escopo; critério de aceite 5 | comando `sen swagger` | etapa do `validate` e do `publish` + serviço Swagger validate isolado | decisão do decisor |
| 12 | doc 1 §1 | Swagger 2.0: migrar antes | se o GET vier em 2.0, a etapa não roda; warning; o fluxo segue | 11 de 40 APIs do consulting estão em 2.0 (I-6) |
| 13 | — | não previsto | erro no contrato do dev aborta antes de qualquer escrita (exit 1); problema da plataforma vira warning no `-o` (exit 0), sem rollback | decisão do decisor |
| 14 | — | não previsto | aviso de descrição abaixo dos mínimos do completeness | o contrato entra na nota (I-7) |
| 15 | — | não previsto | contrato sem mudança não gera PUT de swagger | cada PUT de swagger recria os interceptors |

**D15 — Operação órfã sai do documento.** Medido na 425 em 2026-10-27, nas revisões 1 e 2: quando o repositório tira um método de um path que mantém outro (`POST /c1-pura` saindo, `GET /c1-pura` ficando), a E3 tira a operação do fluxo, mas o Manager a deixa no swagger. Como o PUT de swagger recria o fluxo a partir do documento, gravá-la de volta punha a rota de novo no fluxo, com os interceptors que ela tinha, a cada execução; a C4 só avisava ("está no Manager mas não foi enviada"). Path inteiro e recurso inteiro removidos saem do swagger certo. Por isso, em C2, o documento perde toda operação fora do repositório, e o path que fica sem operação; a diferença basta para haver PUT (D9), que limpa o swagger. Não há aviso próprio: a remoção da rota já é anunciada pela gravação do fluxo. Decisão do usuário em 2026-10-27.

**D16 — O swagger acompanha o fluxo (válvula).** O Manager nem sempre leva ao swagger o que o PUT da revisão gravou: no ECAD, rota nova fora do swagger (chamado 4058988; API 341 rev 50 com o orquestrador, 2026-10-28); no consulting, a API 200 rev 2 com rota e 3 interceptors fora do swagger, e a API 3 rev 19 com itens a mais no fluxo; na 425, com várias revisões, swaggers que nasceram ou ficaram com marcadores de herança apontando para o pai errado ou para chave que não existe, e PUTs da revisão que deixaram de atualizar o swagger (I-11). Como o PUT do swagger refaz o fluxo a partir dos `x-*`, gravar o GET como veio travava a documentação (rota ausente) ou levava ao runtime o que o Manager deixou velho (interceptor, marcador) — este segundo caso sem aviso antes do PUT. Por isso, em C2:

1. os `x-*` são montados do fluxo lido na E3.1 (`written.published`, sem chamada nova) e comparados com os do GET: sem as chaves locais, o `parent-id` resolvido para o item pai, nulo, ausente, `x-interceptors` vazio e `x-api-broken: false` equivalentes, timeout como texto; entram também a `description` da operação e a do recurso;
2. iguais → o documento é o GET, como antes; diferentes → o documento é alinhado ao fluxo: rota que falta é criada (com a `description` do fluxo; os campos do contrato vêm do repositório na montagem), rota e recurso que o fluxo não tem saem, e os `x-*` da raiz, de `x-resources` e de cada operação passam a ser os do fluxo, com as chaves renumeradas (raiz, depois cada recurso e suas operações) e o `parent-id` traduzido para a chave do pai;
3. o nome do tipo de interceptor segue a regra "maiúsculas com `_`", com as exceções medidas: `Digital signature` → `APIKEY_DIGITAL_SIGNATURE`, `JWT validation` → `JWT`, `Time token validation`/`generator` → `TIMETOKEN_VALIDATION`/`TIMETOKEN_GENERATOR`, `XSLT` → `XSL_TRANSFORMATION`, `GZip pack`/`unpack` → `GZIPPACK`/`GZIPUNPACK`, `Java` → `CUSTOM_JAVA` (39 tipos conferidos, I-11); timeout só de dígitos vai como número;
4. não alinha — `not_updated`, fluxo mantido, exit 0 — quando o fluxo usa o que o swagger não carrega (`certificateId`, `connector`, `async`, `urls`, `instruction`) ou um marcador aponta para pai fora da revisão;
5. o que foi alinhado vai só no `-o`, em `documentation.aligned` (D8). A C4 continua conferindo que o fluxo depois do PUT do swagger é o da E3.1.

O alinhamento também destrava a revisão: na 425, depois do swagger alinhado, os PUTs seguintes da revisão voltaram a sincronizar (I-11). Decisão do usuário em 2026-10-28: alinhar só quando diverge; aplicar a regra a tipo não medido.

### Fora de escopo

- O repositório que puxa a API do Manager (importador): passa a puxar o contrato, mas é outro repositório. O `repo_materializer` daqui não é ligado a nenhum comando e fica como está.
- Comando que exponha o Swagger validate ao dev.
- Conversão de Swagger 2.0.
- Validador OpenAPI genérico.

### Riscos

- **PUT de swagger recria os interceptors a cada gravação.** Mitigado pela D9 (sem mudança, sem PUT) e pela conferência de runtime (D10). Divergência de runtime é warning, sem rollback — decisão do decisor. Itens fora de `FIRST`/`SECOND` não são conferidos nesta fase (D12).
- **Gate do Adaptive Governance no PUT de swagger (I-1, E-3 da V-28):** não medido, por decisão (o desenho trata os dois desfechos); um 412 cai na D8.
- **Swagger 2.0 é comum:** 11 de 40 APIs do consulting (I-6). Nelas a etapa não roda (D8) até a migração, que é pré-requisito do APIOps.
- **O contrato mexe no completeness (I-7):** contrato com descrições curtas ou vazias baixa a nota; bem descrito, a sobe. Regravar o mesmo documento não muda a nota (97 antes e depois da restauração). No `validate` a nota é informativa, mas o gate de 70% trava a promoção para DEV+. Mitigado pelos avisos da D6.
- **O Manager dessincroniza o swagger do fluxo (D16):** a causa não é conhecida; apareceu com várias revisões na API e em revisão criada a partir de outra. A válvula depende de o PUT do swagger aceitar o documento alinhado; recusa cai na D8. Campos do fluxo sem extensão no swagger (`certificateId`, `connector`, `async`, `urls`, `instruction`) travam o alinhamento; o PUT de swagger sem alinhamento já não os carregava, e nenhuma API do consulting os usa.
- **Rollout:** com a D4, repositório puxado antes do ajuste do importador falha na validação. A versão só vai para uso depois de puxar os repositórios de novo.
