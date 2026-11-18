## MODIFIED Requirements

### Requirement: Deploy runs only in the pipeline

O comando SHALL rodar apenas com `EXECUTION_MODE=pipeline`. Fora da esteira ele MUST abortar com
`exit 1` antes de autenticar e de qualquer chamada HTTP. A mensagem MUST NOT citar o modo de execução
nem variáveis da esteira. O comando MUST NOT pedir confirmação interativa.

#### Scenario: Dev tenta deployar da máquina
- **WHEN** o comando roda com `EXECUTION_MODE` ausente ou `local`
- **THEN** encerra com `exit 1` e a mensagem "O deploy é feito só pela esteira: o comando não roda
  na sua máquina. A promoção para DEV, HML e PRD acontece no merge da branch
  correspondente.\n\nNenhum deploy foi feito.", sem chamada HTTP

### Requirement: Machine-readable output contract

Com `--output json|yaml`, o comando SHALL emitir o documento `apiops.sen-deploy/v1` com `schema`,
`generatedAt`, `executionMode`, `api`, `revision`, `environment`, `governance`, `previousState`,
`newState`, `deployment` e `warnings`. `executionMode` MUST estar presente só quando o modo é
`pipeline`, o único em que o comando roda. O documento MUST NOT conter token, variáveis de ambiente
nem dump cru do wire. Em `json`/`yaml` nenhum progresso é impresso.

#### Scenario: Esteira consome o resultado
- **WHEN** a esteira roda `sen deploy -o json` e o deploy é conferido
- **THEN** o stdout contém só o documento, com `executionMode = "pipeline"`,
  `deployment.status = "SUCCESS"` e `environment.managerId` igual ao alvo
