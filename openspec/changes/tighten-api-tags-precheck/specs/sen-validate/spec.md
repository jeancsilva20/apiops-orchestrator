## MODIFIED Requirements

### Requirement: Pré-check confere as tags declaradas em apiTags

Antes de qualquer escrita, o pré-check SHALL conferir cada item de `apiTags` contra o catálogo do Adaptive Governance. O comando SHALL abortar com `exit 1`, antes do bloqueio de governança, quando o `attributeName` não existir no catálogo, quando o atributo não tiver tags cadastradas, quando o atributo for declarado sem tag, ou quando uma tag não estiver na lista do atributo. Todos os problemas SHALL sair numa única mensagem, terminando em "Nada foi publicado.". Para atributo inexistente, o comando SHALL sugerir o nome do catálogo apenas quando a diferença for de acentuação e/ou maiúsculas. Avisos do pré-check SHALL aparecer na saída como achados `WARNING`.

#### Scenario: Tag que não pertence ao atributo
- **WHEN** o repositório declara `My new` com a tag `TagInexistente` e o catálogo lista `Tag1` e `Tag2`
- **THEN** o comando aborta com `exit 1`, cita `TagInexistente`, `My new` e as tags válidas, e nenhum `PUT` é emitido

#### Scenario: Atributo declarado sem tag
- **WHEN** o repositório declara `My new` com `tags: []`, exigido ou não pelo stage
- **THEN** o comando aborta com `exit 1`, cita `My new` e as tags válidas, e nenhum `PUT` é emitido

#### Scenario: Atributo sem tags cadastradas
- **WHEN** o repositório declara `CLI` com a tag `Sensedia` e o catálogo não lista nenhuma tag para `CLI`
- **THEN** o comando aborta com `exit 1`, orienta cadastrar as tags no Adaptive Governance, e nenhum `PUT` é emitido

#### Scenario: Atributo inexistente com diferença de maiúscula
- **WHEN** o repositório declara `MY NEW` e o catálogo tem `My new`
- **THEN** o comando aborta com `exit 1`, diz que `MY NEW` não existe no Manager e sugere `My new`

#### Scenario: Atributo inexistente com letras diferentes
- **WHEN** o repositório declara `My news` e o catálogo tem `My new`
- **THEN** o comando aborta com `exit 1`, diz que `My news` não existe no Manager, sem sugestão

#### Scenario: Vários problemas
- **WHEN** o repositório declara um atributo inexistente, um atributo sem tags no catálogo e uma tag fora da lista
- **THEN** os três aparecem na mesma mensagem e o comando aborta com `exit 1`
