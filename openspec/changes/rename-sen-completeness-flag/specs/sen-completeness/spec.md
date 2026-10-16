## MODIFIED Requirements

### Requirement: Grammar of the sen completeness command

The CLI SHALL expose a top-level command `sen completeness`. `--id <id_manager>` MUST be mandatory and `--revision <id_interno>` MUST be mandatory (the `REV ID` shown by the drill-down `sen list api --id X --revisions`). Missing `--revision` (or `--id`) SHALL produce a pre-network validation error with `exit 1`, pointing to `sen list api --id X --revisions`, with zero HTTP calls. The command MUST support `--score-only`, `-o text|json|yaml` (default `text`) and `-v` (verbosity only, never format).

#### Scenario: User runs without --revision
- **WHEN** user runs `sen completeness --id 375` without `--revision`
- **THEN** CLI prints a PT-BR pre-network error guiding `sen list api --id X --revisions` and exits with code 1, without emitting any HTTP call

#### Scenario: User runs without --id
- **WHEN** user runs `sen completeness --revision 5513` without `--id`
- **THEN** CLI prints a PT-BR pre-network error citing the mandatory `--id` flag and exits with code 1, without emitting any HTTP call

#### Scenario: Flags accepted
- **WHEN** user runs `sen completeness --id 375 --revision 5513 --score-only -o json -v`
- **THEN** the parser accepts all flags and proceeds normally
