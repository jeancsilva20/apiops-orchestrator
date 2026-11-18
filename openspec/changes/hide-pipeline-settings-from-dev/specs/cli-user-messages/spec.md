## ADDED Requirements

### Requirement: Outputs outside the pipeline do not reveal pipeline settings

Fora da esteira (`EXECUTION_MODE` ausente, `local` ou inválido), nenhuma saída da CLI (stdout,
stderr, `--help` e documentos `json`/`yaml`) MUST citar `EXECUTION_MODE`, o valor do modo de
execução, "modo local", "modo pipeline", `TARGET_REVISION_NUMBER`, `TARGET_ENVIRONMENT_ID` ou
`TEMPLATE_API_ID`. As saídas MAY citar `SEN_CREDENTIALS`, `AUTH_HOST` e `AUTH_LOGIN_PATH`.

#### Scenario: Recusa do deploy na máquina do dev
- **WHEN** o dev roda `sen deploy` na própria máquina
- **THEN** a mensagem fala em "sua máquina" e "esteira" e não contém nenhum dos nomes proibidos

#### Scenario: Ajuda dos comandos
- **WHEN** o dev roda `sen --help`, `sen publish --help` ou `sen deploy --help`
- **THEN** nenhum texto de ajuda contém os nomes proibidos

### Requirement: Pipeline outputs name pipeline settings but never the mode

Na esteira, as saídas MAY citar `TARGET_REVISION_NUMBER`, `TARGET_ENVIRONMENT_ID` e
`TEMPLATE_API_ID`, e MUST NOT citar `EXECUTION_MODE`.

#### Scenario: Variável ausente na esteira
- **WHEN** a esteira roda `sen deploy` sem `TARGET_ENVIRONMENT_ID`
- **THEN** a mensagem nomeia `TARGET_ENVIRONMENT_ID` e não contém `EXECUTION_MODE`

### Requirement: Invalid configuration names only what the mode allows

Quando a configuração não carrega, a mensagem SHALL listar as chaves com problema que o modo permite
nomear e encerrar com `exit 1`, sem stacktrace. O modo é considerado esteira apenas quando o valor
bruto de `EXECUTION_MODE`, normalizado, é `pipeline`.

#### Scenario: Credencial ausente
- **WHEN** `SEN_CREDENTIALS` não está definida em nenhuma fonte
- **THEN** a mensagem nomeia `SEN_CREDENTIALS`

#### Scenario: Revisão inválida na esteira
- **WHEN** `EXECUTION_MODE=pipeline` e `TARGET_REVISION_NUMBER=abc`
- **THEN** a mensagem nomeia `TARGET_REVISION_NUMBER`

### Requirement: Unnamed configuration problems get a generic message

Havendo chave com problema que o modo não permite nomear, a mensagem SHALL acrescentar "Há outra
configuração inválida. Fale com o time da plataforma." Sem nenhuma chave nomeável, a mensagem SHALL
ser só "A configuração do sen é inválida. Fale com o time da plataforma."

#### Scenario: Modo inválido na máquina do dev
- **WHEN** `EXECUTION_MODE=xyz`
- **THEN** a mensagem é "A configuração do sen é inválida. Fale com o time da plataforma.", sem
  nomear a variável

#### Scenario: Credencial ausente e modo inválido
- **WHEN** `SEN_CREDENTIALS` não está definida e `EXECUTION_MODE=xyz`
- **THEN** a mensagem nomeia `SEN_CREDENTIALS` e acrescenta "Há outra configuração inválida. Fale
  com o time da plataforma."

### Requirement: Help texts in Portuguese

O texto de ajuda dos apps (`sen`, `sen list`), de todos os comandos e de todas as opções SHALL estar
em português. Os rótulos gerados pelo Typer/Click estão fora deste requisito.

#### Scenario: Ajuda do publish
- **WHEN** o dev roda `sen publish --help`
- **THEN** a descrição do comando e de cada opção está em português
