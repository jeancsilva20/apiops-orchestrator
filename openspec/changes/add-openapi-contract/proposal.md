## Why

O repositório declarativo governa só o runtime da revisão (interceptors, destinos, herança). O contrato OpenAPI — `info.contact`, `tags`, `security`, modelos, `operationId`, `summary`, parâmetros, `requestBody`, respostas e headers — não é versionado: é complementado à mão no swagger do Manager e fica órfão do que o repositório publica (APIOPS-115).

A gravação atual (`PUT /revisions/{id}`) não apaga o contrato, mas também não o escreve. O caminho que escreve é o `PUT /revisions/{id}/swagger`, medido na API-lab 425: ele reescreve a revisão inteira e recria todos os interceptors com ids novos, preservando a semântica quando as extensões `x-*` voltam intactas ([V-28 §7](../../../docs/feat-api-estructure/decisoes-refino-409/V-28-heranca-composta-pela-plataforma.md); medições I-8 e I-8b no [mapa de cenários](../../../docs/feat-contrato-openapi/cenarios-de-teste.md)).

## What Changes

- **Layout:** `components.yaml` novo e opcional na raiz (`schemas`, `securitySchemes`, `responses`, `requestBodies`, `headers`, `examples`); campos de contrato no `api-basic-info.yaml` (`contact`, `tags`, `security`), no `resource.yaml` (`parameters` compartilhados por todas as rotas do recurso) e no arquivo da operação (`operationId`, `summary`, `tags`, `parameters`, `requestBody`, `responses`).
- **Serviço Swagger validate:** validações locais do contrato declarado, isoladas para serem reutilizadas por um comando futuro. Erro aborta o comando **antes de qualquer escrita**, exit 1.
- **Etapa de contrato no `validate` e no `publish`:** depois do PUT da revisão e da conferência atual, lê o swagger, aplica o contrato do repositório e grava. O repositório é a verdade nos campos que governa: **ausente vai em branco**. `servers`, `info.title/version/description`, `x-*` e as seções que o modelo não cobre vêm do GET.
- **Aviso do que some:** o swagger é lido antes da gravação da revisão; o `validate` lista na confirmação o que sai da documentação do Manager, e o `publish` leva o mesmo aviso no `-o`.
- **Conferência nova**, normalizada: contrato como declarado, `x-*` iguais e runtime igual ao que a conferência atual aprovou.
- **Problema da plataforma** (Swagger 2.0, recusa, falha persistente, conferência divergente): warning no `-o`, exit 0, fluxo gravado mantido. **Sem rollback.**
- **Contrato sem mudança não gera PUT** de swagger.

## Capabilities

### New Capabilities

- `openapi-contract`: validação, montagem, gravação e conferência do contrato OpenAPI da revisão.

### Modified Capabilities

- `api-repo-layout`: `components.yaml` e os campos de contrato em cada arquivo.
- `sen-validate`: etapa de contrato, aviso na confirmação, warnings no `-o`.
- `sen-publish`: etapa de contrato e warnings no `-o`.

Os requisitos modificados vivem nas specs das changes `add-sen-validate` e `add-sen-publish`, que precisam ser arquivadas antes desta.

## Impact

- **Código novo** (nomes e docstrings em inglês, padrão do projeto; mensagens ao usuário em pt-BR): `domain/services/openapi_contract.py` (extração, montagem sobre o swagger e comparação, puro), `domain/services/openapi_contract_validator.py` (Swagger validate, puro), `application/services/contract_writer.py` (`ContractWriter`, par do `RevisionWriter`, usado por `validate` e `publish`), `domain/schemas/api-components.schema.json`.
- **Código alterado:** `repo_layout.py` e `repo_importer_service.py` (`components.yaml`), `manager_api_port.py` e `manager_api_adapter.py` (GET e PUT do swagger), `revision_writer.py` (devolve o estado lido na conferência), `validate_service.py`, `publish_service.py`, `cli_adapter.py` (rótulos de etapa e texto da confirmação), schemas `api-basic-info`, `api-resource`, `api-operations` e `catalog.json`.
- **Sem mudança:** montagem e conferência do fluxo (`revision_payload`), `deploy`, formato do `-o` (o resultado da etapa entra como warning nos campos que já existem).
- **Rede:** até três GET e um PUT a mais por execução (GET do swagger antes da revisão; GET, PUT e GET de conferência depois). Sem PUT quando o contrato não mudou.
- **Rollout:** `responses` é obrigatório em toda rota, então repositório puxado antes do ajuste do importador falha na validação. A versão só vai para uso depois que os repositórios forem puxados de novo com o importador que traz o contrato (outro repositório, fora desta change). Campo governado que o repositório não declara apaga, na publicação, a documentação mantida à mão no Manager — com aviso.
- **Completeness:** o Manager avalia o contrato na nota; contrato pouco descrito a baixa (I-7).
- **Swagger 2.0:** 11 de 40 APIs do consulting (I-6); nelas a etapa não roda até a migração.
- **Testes:** unitários das validações, da montagem, da normalização, da etapa e dos dois comandos; bateria opt-in na API-lab 425.
