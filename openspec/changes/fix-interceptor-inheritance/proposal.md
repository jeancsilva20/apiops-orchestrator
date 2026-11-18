## Why

A V-27 publica o fluxo herdado copiado dentro de cada escopo, partindo da W-4: o Manager guardaria o fluxo resolvido, e lista própria não vazia seria o fluxo inteiro do escopo. A medição em runtime de 21/10/2026, na API-lab 425 do consulting, mostrou o contrário ([V-28](../../../docs/feat-api-estructure/decisoes-refino-409/V-28-heranca-composta-pela-plataforma.md)): o Manager compõe o fluxo de cada escopo como **o que o pai executa, menos os itens marcados `REMOVED`, mais os itens próprios**. A UI faz o mesmo (save capturado no mesmo dia).

Efeitos no código atual:

- `inherit: true` com itens copia o herdado para dentro do escopo, e o herdado **executa duas vezes** (rota `s3`: 5 execuções para 3 interceptors);
- `inherit: false` com itens está certo desde o `f018ca5`, mas o item que entra no pai na mesma publicação não é marcado e executa até a próxima publicação;
- `inherit: false` sem itens é tratado como não representável (T06) e a rota segue herdando, embora marcar todo o herdado dê uma rota sem interceptors (rota `s7`);
- a conformidade trata a lista própria como o fluxo inteiro do escopo;
- o importador grava `inherit: false` em escopo que, no Manager, acrescenta itens ao herdado.

## What Changes

- **`inherit: true` com itens:** o escopo guarda só os itens declarados, que executam depois do herdado.
- **`inherit: false` com itens:** sem mudança — os declarados mais uma marcação para cada item que o pai executa.
- **`inherit: false` sem itens:** só as marcações; a rota não executa nada. Sai o aviso de "não representável".
- **Item que entra no pai na mesma publicação:** a marcação aponta para ele pelo `idTemp`. Sai o aviso "rode o comando de novo".
- **Ordem:** a execução é por escopo (herdado primeiro); a `position` ordena só dentro do escopo. Sai o reposicionamento dos itens próprios depois da maior posição herdada.
- **Avisos:** sai o de `inherit: false` sem itens; o de "lista própria cede à herança" muda de texto; entra o de **herdado que o escopo deixa de executar** ao publicar.
- **Conferência pós-publicação:** os itens próprios são comparados com o que o arquivo declara; as marcações, pelo item herdado que removem, e não pelo `parent.id`.
- **Conformidade:** o fluxo de cada escopo é composto como o Manager o executa.
- **Importador:** escopo com itens próprios e sem marcações vira `inherit: true` com os itens; tudo marcado e nada próprio vira `inherit: false` sem itens.
- **Schemas YAML:** a descrição de `inherit` deixa de citar a W-4.
- **Remoção:** `comparar_deriva_de_override` (nunca chamado) e o requisito "Override drift is reported".
- O código separa a decisão do que cada escopo guarda da escrita no PUT de revisão, para que a publicação via swagger do roadmap troque só a escrita.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `api-repo-layout`: regime de herança, remoção por lista completa e avisos de fluxo removido.
- `api-repo-import`: materialização de append, remoção e rota sem interceptors.
- `template-conformance`: fluxo efetivo composto; remove a deriva de override.
- `sen-validate`: conferência pós-publicação das marcações; cenários T06, T07, T08, T11 e T12 da bateria; bateria nova de herança com runtime na API-lab.

Os requisitos alterados vivem nas specs da change `add-sen-validate`, que precisa ser arquivada antes desta. O `sen-publish` usa a mesma montagem e a mesma conferência, e seus requisitos seguem valendo sem delta.

## Impact

- Código alterado: `domain/services/interceptor_flow.py`, `domain/services/revision_payload.py`, `domain/services/template_conformance.py`, `domain/services/repo_materializer.py`, `application/services/validate_service.py`, `domain/schemas/api-resource.schema.json`, `domain/schemas/api-operations.schema.json`.
- Testes: `test_interceptor_flow.py`, `test_revision_payload.py`, `test_template_conformance.py`, `test_repo_materializer.py`, `test_materializer_oracle.py`, `test_validate_service.py`, `test_publish_service.py`; `tests/integration/test_bateria_417.py` (oráculos de T06, T07, T08, T11 e T12); bateria nova `tests/integration/test_bateria_heranca_425.py`.
- Documentação: V-28 nova; notas de revisão em V-25, V-26, V-27, W-3, W-4, W-5, no caderno de testes e no guia de implementação.
- Rede: nenhuma chamada nova nos comandos. A bateria nova escreve na API-lab 425, faz deploy no ambiente 7 e lê o trace das chamadas.
- APIs já publicadas com o código atual: a primeira publicação com a correção tira as cópias do herdado dos escopos com `inherit: true` e itens.
