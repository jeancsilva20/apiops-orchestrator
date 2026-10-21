## ADDED Requirements

### Requirement: Publish runs only in the pipeline

O comando SHALL rodar apenas com `EXECUTION_MODE=pipeline`. Fora da esteira ele MUST abortar com
`exit 1` antes de autenticar e de qualquer chamada HTTP, com mensagem que explique que a publicação é
feita pela esteira e aponte o `sen validate`. A mensagem MUST NOT citar o modo de execução nem
variáveis da esteira. O comando MUST NOT pedir confirmação interativa.

#### Scenario: Dev tenta publicar da máquina
- **WHEN** o comando roda com `EXECUTION_MODE` ausente ou `local`
- **THEN** encerra com `exit 1` e a mensagem "A publicação é feita só pela esteira: o comando não
  roda na sua máquina. Para conferir o repositório contra a governança, use `sen validate`, que
  grava na revisão Draft.\n\nNada foi publicado.", sem chamada HTTP

#### Scenario: Esteira não pergunta
- **WHEN** o comando roda com `EXECUTION_MODE=pipeline` e chega à gravação
- **THEN** nenhuma confirmação é pedida

## MODIFIED Requirements

### Requirement: Target revision resolved by number from configuration

A revisão alvo SHALL ser lida de `TARGET_REVISION_NUMBER` e resolvida pelo `revisionNumber` em
`revisions[]` do `GET /apis/{spec.id}`. A variável MUST estar definida. O comando MUST NOT chamar
`POST /revisions`.

#### Scenario: Esteira publica na revisão do ambiente
- **WHEN** `EXECUTION_MODE=pipeline`, `TARGET_REVISION_NUMBER=2` e a API tem a revisão 2 com id 9175
- **THEN** o comando lê e grava `PUT /revisions/9175`, e nenhuma outra revisão é escrita

#### Scenario: Variável ausente na esteira
- **WHEN** `EXECUTION_MODE=pipeline` e `TARGET_REVISION_NUMBER` não está definida
- **THEN** o comando aborta com `exit 1` antes de qualquer chamada HTTP, nomeando a variável

#### Scenario: Revisão inexistente
- **WHEN** a API não tem revisão de número 4
- **THEN** o comando aborta com `exit 1`, nomeando as revisões disponíveis, sem escrever

#### Scenario: API sem revisões
- **WHEN** `revisions[]` vem vazio
- **THEN** o comando aborta com `exit 1`, sem escrever

### Requirement: Machine-readable output contract

Com `--output json|yaml`, o comando SHALL emitir o documento `apiops.sen-publish/v1` com `schema`,
`generatedAt`, `executionMode`, `api`, `revision`, `governance`, `publication` e `warnings`.
`executionMode` MUST estar presente só quando o modo é `pipeline`, o único em que o comando roda. O
documento MUST NOT conter token nem dump cru do wire. Em `json`/`yaml` nenhum progresso é impresso.

#### Scenario: Esteira consome o resultado
- **WHEN** a esteira roda `sen publish -o json` e a publicação é conferida
- **THEN** o stdout contém só o documento, com `executionMode = "pipeline"`,
  `revision.revisionNumber` igual ao alvo e `publication.verified = true`

### Requirement: Removal is warned before the write

Recurso, rota ou interceptor presente no Manager e ausente do repositório SHALL gerar aviso que nomeie
o que será apagado. O aviso MUST NOT bloquear e MUST sair no resultado.

#### Scenario: Rota removida
- **WHEN** a rota `DELETE /letras/{id}` existe no Manager e não no repositório
- **THEN** o resultado lista a rota em `warnings`, e a gravação segue

## REMOVED Requirements

### Requirement: Local publish requires explicit consent

**Reason**: o `sen publish` deixa de rodar na máquina do dev; sem execução local, não há quem
confirme. A gravação na Draft pela máquina do dev continua no `sen validate`, com confirmação.

**Migration**: o dev usa `sen validate` para gravar na Draft e obter o veredito da governança.
