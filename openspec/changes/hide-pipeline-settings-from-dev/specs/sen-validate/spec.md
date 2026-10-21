## ADDED Requirements

### Requirement: Local validate always targets the Draft

Fora da esteira (`EXECUTION_MODE` ausente ou `local`), o comando SHALL gravar sempre na revisão de
número 1 (Draft) e MUST NOT ler `TARGET_REVISION_NUMBER`. Na esteira, a revisão alvo SHALL continuar
sendo lida de `TARGET_REVISION_NUMBER`, com `1` quando ausente.

#### Scenario: Variável definida na máquina do dev
- **WHEN** o comando roda fora da esteira com `TARGET_REVISION_NUMBER=3`
- **THEN** a revisão alvo é a 1 (Draft), nenhuma recusa é emitida e nenhuma saída cita a variável

#### Scenario: Esteira grava na revisão configurada
- **WHEN** o comando roda com `EXECUTION_MODE=pipeline` e `TARGET_REVISION_NUMBER=2`
- **THEN** a revisão alvo é a 2

### Requirement: Execution mode only in pipeline output

No documento `apiops.sen-validate/v1`, o campo `executionMode` MUST estar presente só quando o modo é
`pipeline`, com o valor `"pipeline"`; fora da esteira ele MUST ser omitido. O painel de texto MUST NOT
exibir o modo de execução.

#### Scenario: JSON na máquina do dev
- **WHEN** o comando roda fora da esteira com `-o json`
- **THEN** o documento não contém a chave `executionMode`

#### Scenario: JSON na esteira
- **WHEN** o comando roda com `EXECUTION_MODE=pipeline` e `-o json`
- **THEN** o documento contém `executionMode = "pipeline"`
