## ADDED Requirements

### Requirement: Tenant without Adaptive Governance

Before reading the revision, the command SHALL check whether the Manager has the Adaptive Governance. When the tenant has no AG, the command SHALL NOT call the completeness endpoint and SHALL exit with code 3, printing "A checagem de completude não está disponível: cliente não possui o Adaptive Governance contratado.". When it is not possible to tell whether the AG is active, the command SHALL keep the current behavior.

#### Scenario: Tenant without AG
- **WHEN** the attributes catalog of the AG answers 403 with the "Governance module enabled" message
- **THEN** the CLI prints the PT-BR message above, makes no completeness call and exits with code 3

#### Scenario: Inconclusive detection
- **WHEN** the attributes catalog fails with an error other than 403 in all three attempts
- **THEN** the command reads the completeness as today, following the existing exit code matrix
