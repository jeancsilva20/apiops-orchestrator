## MODIFIED Requirements

### Requirement: Exit code matrix

The command SHALL implement: pre-network input errors (`exit 1`); platform refusals on the Manager call (401, 403, 404 revision not found, other 4xx, exhausted 5xx) and unexpected failures with honest PT-BR messages orienting next steps (`exit 2`); real emptiness and satellite failures (`exit 0`). For `404` specifically, the message SHALL orient `sen list api --id X --revisions` to rediscover a valid revision id. Refusals outside 401/403/404 (e.g. `409`, `413`, `422`) and unexpected failures SHALL show the CLI's standard internal-error message, shared with `sen list`: it SHALL NOT orient `sen login` and SHALL NOT echo the HTTP status, the HTTP title, the platform error code or the exception text. Diagnostic data (status, platform error code, platform request id and, for unexpected failures, type and stacktrace) SHALL go to the log only. No stacktrace is ever shown; failures shall never abort mid-render leaving half-visible tables.

#### Scenario: Revision not found
- **WHEN** the Manager responds `404` for the informed revision
- **THEN** the CLI prints a PT-BR message suggesting `sen list api --id X --revisions` and exits with code 2

#### Scenario: Unauthorized
- **WHEN** the Manager responds `401` (session expired)
- **THEN** the CLI prints a PT-BR message orienting `sen login` and exits with code 2

#### Scenario: Refusal unrelated to credentials
- **WHEN** the Manager responds a 4xx outside 401/403/404 (e.g. `413` or `422`)
- **THEN** the CLI prints the standard PT-BR internal-error message, without orienting `sen login` and without showing status, title or platform code, and exits with code 2

#### Scenario: Unexpected failure
- **WHEN** an unforeseen failure happens while the command runs
- **THEN** the CLI prints the standard PT-BR internal-error message without the exception text and exits with code 2, while type and stacktrace go to the log only

#### Scenario: Success
- **WHEN** the Manager responds `200` with a valid payload
- **THEN** the command exits with code 0 regardless of the score value
