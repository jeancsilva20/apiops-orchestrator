## 1. Registro das decisões nos docs da feature

> Regra 1 do AGENTS.md: decisão de layout é gravada nos docs **antes** de virar código.

- [x] 1.1 Abrir `docs/feat-api-estructure/d020-stage-do-adaptive-governance.md` com a regra do stage lido em runtime, carregando a evidência dos GETs de 2026-10-15 (revisions 9161 e 9175 em `500/1402`; par autoconsistente; PUT aceito não move o ponteiro)
- [x] 1.2 Fechar a **V-18** com `all.yaml`, a gramática do escopo raiz e a regra de arquivo base obrigatório pelo nome exato
- [x] 1.3 Fechar a **V-25 / D-2 / P-4** com a lista completa explícita, citando o T06 como prova de que é a única forma expressável
- [x] 1.4 Fechar a **P-2 / D-3** com o aborto nos dois modos, incluindo `spec.template` vazio e a ambiguidade do 403
- [x] 1.5 Fechar a **D-5** registrando que a validação de shape passa para a API template, e que os 7 schemas são retirados
- [x] 1.6 Fechar a **W-2** com o aborto no `Custom` inexistente, registrando que a reposição por revisão antiga foi descartada
- [x] 1.7 Fechar a **D-4 / P-3** com o snapshot da régua (`id`, `revisionNumber`, hash) no contrato de saída
- [x] 1.8 Atualizar a árvore da **D-005 §4** para `all.yaml` e a **V-11 conformidade §4** com a granularidade do `content` (nativos comparam, `Custom` casa por id)
- [x] 1.9 Marcar na tabela §9 do `plano-comandos-sen.md` que **D-14**, **D-7** e **D-8** já foram fechadas por evidência no §8.4 do próprio documento
- [x] 1.10 Corrigir os cinco defeitos do `guia-implementacao-sen-validate.md`: §1 (o modelo de interceptors não está certo), §3 (fallback do `Custom`), §3 (404 vira `ManagerApiTransportRejectedError`, não `KeyError`), §4.2 (`inherit: false` sem lista herda), §10 (os `*-default-interceptors` não foram removidos)
- [x] 1.11 Gerar o exemplo anotado completo de `all.yaml` em `exemplo-layout-final/`, no padrão de `padrao-exemplos-anotados.md` (regra 5 do AGENTS.md)
- [x] 1.12 Atualizar `fila-templates-schemas.md` com a depreciação dos 7 schemas, `extrair_estrutura.py:354` e a regeração dos repos de exemplo
- [x] 1.13 Fechar a **D-9** registrando a reconciliação do canônico: o `validate` local escreve sob confirmação `s/n` (guarda 2), e o *"uso exclusivo da esteira"* passa a significar "sem publicação acidental", não "sem publicação local"
- [x] 1.14 Registrar que `Custom` segue referenciado por **id numérico**, estável dentro de um ambiente, com a validação de troca sendo responsabilidade do dev — e retirar a portabilidade da lista de estacionados ou marcar o motivo de permanecer lá
- [x] 1.15 Fechar a **P-8** com o escopo reduzido: `PUT /revisions/{id}` e inferências do AG já validados; herança em runtime é Non-Goal; resta a equivalência `''` ↔ `null` na escrita, que roda na API dedicada

## 2. Fase 0 — demolição e contrato de borda

- [x] 2.1 Remover os 7 `domain/schemas/*-default-interceptors.schema.json` e tudo que os referencia, verificando que nenhum teste existente quebra
- [x] 2.2 Atualizar `domain/schemas/catalog.json` e os schemas remanescentes para o layout canônico
- [x] 2.3 Estender `config/settings.py` com `EXECUTION_MODE`, `TEMPLATE_API_ID` e `TARGET_REVISION_NUMBER`, respeitando a precedência `process env > .sen > .env`
- [x] 2.4 Criar `application/exceptions/validate_exceptions.py` com `ValidateError` e as subclasses `IdentidadeDivergenteError`, `TemplateAusenteError`, `LayoutInvalidoError`, `CustomInexistenteError`, `ReguaInalcancavelError`, `PublicacaoDivergenteError` (exit 1) e `GovernanceBlockedError` (exit 3)
- [x] 2.5 Criar `domain/models/validate_view.py` com dataclass `frozen=True` e `to_document()` emitindo o contrato `apiops.sen-validate/v1`, incluindo o bloco de snapshot da régua
- [x] 2.6 Adicionar o comando `sen validate` em `cli_adapter.py` seguindo a forma do `sen completeness`, com `--repo`, `--output`, `--verbose` e os subcomandos `structure`/`template`/`draft` marcados `hidden=True`
- [x] 2.7 Montar `build_validate_service_factory()` em `main.py` e registrá-la no contexto, de forma preguiçosa
- [x] 2.8 Implementar o renderizador de texto para leitura no PowerShell, e garantir que `json`/`yaml` serializam a mesma árvore
- [x] 2.9 Testar a borda: `--output json` conforme ao schema, exit codes `0`/`1`/`3`, ausência de credencial em qualquer saída

## 3. Fase 1 — import e layout

- [x] 3.1 Criar `domain/services/repo_layout.py` com slug, desambiguação legível, truncamento com marca, orçamento de caminho e resolução do método pelo nome do arquivo
- [x] 3.2 Transplantar a lógica de `extrair_estrutura.py` para o importer de produção, aplicando os dois reparos de serialização (escalar iniciado por indicador YAML citado; string numérica preservada)
- [x] 3.3 Implementar a descoberta da E1 com `all.yaml` e `resource.yaml` obrigatórios pelo nome exato, abortando na ausência antes de qualquer rede
- [x] 3.4 Implementar a partição governado (`FIRST`/`SECOND`) × preservado, devolvendo o preservado intacto
- [x] 3.5 Fazer o import materializar remoção como lista completa explícita, em vez de comentário
- [x] 3.6 Fazer o import falhar alto em estado remoto não representável pelo layout
- [x] 3.7 Reescrever `application/services/repo_importer_service.py` sobre as peças acima
- [x] 3.7a ~~Reescrever `JsonToYamlService`~~ → **remover a ilha de materialização do layout antigo**, que não tinha consumidor em produção (e cujo `RevisionFileGenerator` já importava módulo inexistente). O `xfail` saiu com a causa, não com a marcação
- [x] 3.7b Despacho de schema por **caminho** (`escolher_schema` + `CatalogSchemaValidator`), com casamento segmento a segmento para o `*` não atravessar `/`
- [x] 3.7c `json_to_yaml_enum` removido com a ilha. A fixture de `test_repo_validator.py` permanece **coerente**: ela testa o `RepoValidator`, que valida o layout antigo e sustenta o pipeline bare — os dois saem juntos na fase 3
- [x] 3.8 Testar contra o oracle: as 6 APIs reais produzem os 155 YAML idênticos à saída de referência
- [x] 3.9 Regerar os repositórios de exemplo com `all.yaml` e os reparos de serialização
- [x] 3.10 Adicionar o subcomando oculto `sen validate structure` (`hidden=True`), que mostra a estrutura descoberta na E1 — adiado da fase 0 porque antes da descoberta não há o que mostrar
- [x] 3.11 **Defeito encontrado e corrigido:** `display_output` renderizava `-o json`/`-o yaml` pelo `rich.Syntax`, que quebra a linha na largura do console e produzia **JSON inválido** para qualquer valor longo. Atinge também `sen completeness` e `sen list`, e derrota o propósito do formato. Agora a saída legível por máquina sai crua quando stdout não é terminal, com realce e `soft_wrap` apenas para leitura humana

## 4. Fase 2 — conformidade com a régua

- [x] 4.1 Implementar a resolução da régua por modo de execução (`spec.template` em local, variável de ambiente em pipeline, com `WARNING` na divergência)
- [x] 4.2 Implementar a leitura da régua em um único `GET /apis/{id}`, consumindo `lastRevision`
- [x] 4.3 Implementar o aborto por régua inalcançável (`404`, `403`, rede) e por `spec.template` vazio, com mensagem do `403` nomeando as duas causas possíveis
- [x] 4.4 Criar `domain/services/template_conformance.py` comparando por sequência, com `content` nos tipos nativos e casamento por `customInterceptorId` no `Custom`
- [x] 4.5 Implementar a normalização de escalar numérico antes da comparação, para evitar achado falso entre `"1000"` e `1000`
- [x] 4.6 Implementar a classificação `INFO` (acréscimo) e `WARNING` (override, remoção, alteração), tratando a raiz da revision item a item, nunca como append
- [x] 4.7 Implementar o `WARNING` de deriva de override, comparando o escopo também com o fluxo do pai
- [x] 4.8 Implementar a verificação de existência do `Custom` referenciado, abortando e nomeando o id, sem repor conteúdo de revisão antiga
- [x] 4.9 Preencher o snapshot da régua na `ValidateView` com `id`, `revisionNumber` e hash do fluxo comparado
- [x] 4.10 Testar contra o oracle: exatamente os 4 achados previstos nas APIs 409 e 417
- [x] 4.11 Adicionar o subcomando oculto `sen validate template` (`hidden=True`), que mostra a régua lida e seu snapshot — adiado da fase 0 pelo mesmo motivo

## 5. Fase 3 — publicação

> **Bloqueio declarado:** a tarefa 5.1 é pré-requisito de todas as demais deste grupo.

- [x] 5.1 ~~Provisionar API dedicada~~ — **resolvido em 2026-10-15:** a **API 417** é específica deste projeto e serve como alvo de escrita. Ela já atende aos requisitos levantados: Draft (rev 9161) sem deploy, stage 1402 com `attributesRequisites`, fluxo na raiz + recurso + operação, `Custom` referenciados e um caso de supressão (`GET /tarefas`)
- [x] 5.2 Validar na API dedicada a equivalência `''` ↔ `null` na escrita, fechando o que resta da P-8
- [x] 5.3 Estender `ManagerApiPort` com `get_revision`, `update_revision`, `get_workflow` e `list_attributes`
- [x] 5.4 Implementar os métodos no `manager_api_adapter.py`, e fazer `get_custom_interceptor_by_id` devolver `None` no `404` capturando `ManagerApiTransportRejectedError`
- [x] 5.5 ~~Separar `interceptors_model.py`~~ → **o caminho novo não passa por ele.** O publisher opera sobre dicts do wire, como o materializador, e a aritmética de identidade vive em `interceptor_flow`, com contador global de `idTemp` e `id: None` em item novo. O modelo legado recebeu nota explícita do defeito do W-9 e sai junto com o `ConversorService` na substituição do publisher — removê-lo agora quebraria o pipeline bare sem substituto pronto
- [x] 5.6 ~~Ajustar `api_operations_model` e `resources_model`~~ → **mesma razão da 5.5.** A validação do shape declarativo é feita pelos schemas (`api-operations`, `api-resource`, `api-root-scope`), que já descrevem `destination` como objeto e `inherit`; duplicá-la em pydantic criaria duas fontes de verdade para o mesmo contrato
- [x] 5.7 Criar `domain/services/interceptor_flow.py` com partição, casamento, construção de item novo, contador **global** de `idTemp` e preservação de `position` nos itens reusados
- [x] 5.8 Implementar a preservação integral do fluxo herdado em `inherit: true`, publicando o resolvido e não o delta — **revisto na fase 6 (V-27)**: preservar a lista remota apagava o herdado quando o escopo ainda não tinha lista própria
- [x] 5.9 Criar `application/services/governance_precheck_service.py` calculando `exigidos(mustHave) - presentes`, sem parsear `messages[]`, lendo workflow e stage da revisão alvo
- [x] 5.10 Criar `application/services/validate_service.py` orquestrando E1→E4, recebendo ports e o callable de confirmação injetado pela CLI
- [x] 5.11 Implementar a E3 como um único `PUT /revisions/{id}`, com `workflowId`/`workflowStageId` reenviados intactos e sem qualquer `PUT /apis/{id}` ou `POST /revisions`
- [x] 5.12 Implementar a conferência pós-publicação comparando enviado × publicado em operações, interceptors por escopo e recursos vazios, tratando divergência como falha
- [x] 5.13 Ligar a E4 ao serviço de completeness existente, em regime informativo
- [x] 5.13a Adicionar o subcomando oculto `sen diag draft` (`hidden=True`), que mostra o estado da revisão alvo — adiado da fase 0 pelo mesmo motivo
- [x] 5.14 Testar a cascata com port fake: guardas, ordem das etapas, tudo-ou-nada
- [x] 5.15 Testar o pré-check de governança com catálogo fake, incluindo requisito que muda entre execuções
- [x] 5.16 Construir o arnês da bateria de aceitação: backup completo da API e de todas as revisions antes da primeira escrita, alteração do repositório por cenário, execução do comando, releitura por `GET` e restauração do baseline — com restauração também disponível por comando
- [x] 5.17 Executar os 10 cenários do caderno (T01 a T08, T10, T11) contra a **API 417** (tarefa 5.1), exigindo que cada veredito venha da releitura e nunca do código HTTP
- [x] 5.18 Confirmar, ao fim da bateria, que o estado da API é idêntico ao baseline em nome, descrição, tags, `basePath`, recursos, operações e interceptors

## 6. V-27 — o fluxo efetivo resolvido no repositório

- [x] 6.1 Gravar a decisão em `docs/feat-api-estructure/decisoes-refino-409/V-27-fluxo-resolvido-no-repositorio.md`, com a evidência do T11 e os custos assumidos, antes de qualquer código (regra 1 do AGENTS.md)
- [x] 6.2 Registrar a V-27 no índice do refino e marcar a V-26 como revista na publicação
- [x] 6.3 Criar `FluxoDoEscopo` e `resolver_fluxo_declarado` em `interceptor_flow.py`, cobrindo os quatro casos da D5 revista
- [x] 6.4 Reescrever `montar_fluxo_do_escopo` para traduzir um fluxo já resolvido, sem decidir herança, e manter a `position` dos reusados (W-3)
- [x] 6.5 Excluir o tombstone do pool de casamento: ele tem a mesma chave do item que suprime, e reaproveitá-lo publicaria `status: REMOVED` no lugar do item vivo
- [x] 6.6 Descer a resolução em `revision_payload.montar`: `all.yaml` alimenta os recursos, cada recurso alimenta suas operações
- [x] 6.7 Trocar o aviso de "declaração sem efeito" pelos três avisos de remoção: lista própria que cede à herança, `inherit: false` sem itens, e raiz esvaziada pelo `all.yaml`
- [x] 6.8 Corrigir o importador: lista própria não vazia sempre materializa `inherit: false` com a lista completa, para o round-trip import→publish fechar
- [x] 6.9 Conferir na E3.1 os itens **vivos** por escopo e reportar tombstone remanescente como divergência (V-27 §8, E-2)
- [x] 6.10 Corrigir o oráculo do T11 na bateria e acrescentar o T12 (restaurar herança + acrescentar numa só declaração)
- [ ] 6.11 Rodar a bateria 417 com autorização explícita e fechar as pendências empíricas E-1 (`[]` na raiz) e E-2 (tombstone remanescente)

## 7. Mensagens e apresentação

- [x] 7.1 Inventariar as 23 mensagens de borda em `docs/feat-api-estructure/revisao-mensagens-sen-validate.md`, agrupadas por canal, para revisão do usuário
- [x] 7.2 Reescrever as mensagens pelas três regras: começar pelo fato, separar consequência de instrução, nenhuma marcação de cor no texto
- [x] 7.3 Aplicar o glossário (T2): régua -> API-template, tombstone -> marcação de interceptor removido, tenant -> ambiente
- [x] 7.4 Remover do texto do usuário as citações de documento interno e a caixa alta como ênfase (T1, T3)
- [x] 7.5 Quebrar em lista o que quebrava no meio do nome em terminal estreito: atributos faltantes da governança e divergências da conferência (T5)
- [x] 7.6 Reescrever o prompt de confirmação: ele sugeria deploy. A frase explicativa fica no serviço, a pergunta de sim/não na borda
- [x] 7.7 Trocar `(gate: >=70
## 7. Mensagens e apresentação

- [x] 7.1 Inventariar as 23 mensagens de borda em `docs/feat-api-estructure/revisao-mensagens-sen-validate.md`, agrupadas por canal, para revisão do usuário
- [x] 7.2 Reescrever as mensagens pelas três regras: começar pelo fato, separar consequência de instrução, nenhuma marcação de cor no texto
- [x] 7.3 Aplicar o glossário (T2): régua → API-template, tombstone → marcação de interceptor removido, tenant → ambiente
- [x] 7.4 Remover do texto do usuário as citações de documento interno e a caixa alta como ênfase (T1, T3)
- [x] 7.5 Quebrar em lista o que quebrava no meio do nome em terminal estreito: atributos faltantes da governança e divergências da conferência (T5)
- [x] 7.6 Reescrever o prompt de confirmação: ele sugeria deploy. A frase explicativa fica no serviço, a pergunta de sim/não na borda
- [x] 7.7 Trocar `(gate: ≥70% — trava em DEV+, não aqui)` por `Quality gate: ≥70%`, com queda para `>=` em console sem o glifo
- [x] 7.8 Apresentar o resultado no padrão do `sen login` e do `sen list`: caixa de identidade, tabela de achados, grade de rótulos, largura única
- [x] 7.9 Separar os avisos do repositório da tabela de conformidade, via `ESCOPO_REPOSITORIO`, porque são textos de várias frases
- [x] 7.10 Narrar as etapas da cascata numa barra de progresso, com `progresso` opcional injetado pela borda
- [x] 7.11 Silenciar o progresso em `-o json`/`-o yaml` e pausar a barra durante a confirmação
- [x] 7.12 Cobrir com teste: progresso não contamina saída de máquina, ordem das etapas, texto da confirmação sem promessa de deploy, ordem das hipóteses no 403
