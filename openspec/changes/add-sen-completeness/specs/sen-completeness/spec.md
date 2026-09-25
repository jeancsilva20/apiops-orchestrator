# Spec — sen-completeness (delta)

## ADDED Requirements

### Requirement: Grammar of the sen completeness command

The CLI SHALL expose a top-level command `sen completeness`. `--api-id <id_manager>` MUST be mandatory and `--revision <id_interno>` MUST be mandatory (the `REV ID` shown by the drill-down `sen list api --id X --revisions`). Missing `--revision` (or `--api-id`) SHALL produce a pre-network validation error with `exit 1`, pointing to `sen list api --id X --revisions`, with zero HTTP calls. The command MUST support `--score-only`, `-o text|json|yaml` (default `text`) and `-v` (verbosity only, never format).

#### Scenario: User runs without --revision
- **WHEN** user runs `sen completeness --api-id 375` without `--revision`
- **THEN** CLI prints a PT-BR pre-network error guiding `sen list api --id X --revisions` and exits with code 1, without emitting any HTTP call

#### Scenario: Flags accepted
- **WHEN** user runs `sen completeness --api-id 375 --revision 5513 --score-only -o json -v`
- **THEN** the parser accepts all flags and proceeds normally

### Requirement: Fetch completeness for any revision from the Manager

The command SHALL fetch the completeness report of the informed revision exclusively from the Manager endpoint `GET /api-manager/api/v3/revisions/{rid}/completeness`, whose response carries `{completenessScore: number, suggestions: string[]}`. Any revision reachable in the platform SHALL be consultable: historical revisions MUST NOT be refused by the command itself. The command SHALL NOT call Adaptive Governance routes (`search`, `maturity-reports`) nor Connect Catalog routes. The satellite api-finder call (context/ownership enrichment) MAY degrade softly: when it fails, the command SHALL still succeed with `exit 0` and the absence itself is the signal — API `name`/`version`/`context` fields render as `-` (no narrator block, no collect-state in any output).

#### Scenario: Historical revision is consultable
- **WHEN** user runs `sen completeness --api-id 375 --revision 5501` (a non-last revision)
- **THEN** the CLI performs `GET /api-manager/api/v3/revisions/5501/completeness` and renders the returned completeness for that revision (no synthetic refusal, no exit 2 for being an old revision)

#### Scenario: Identity lookup degrades softly
- **WHEN** the api-finder lookup fails but the Manager call succeeds
- **THEN** the output renders the raw manager id (e.g. `API: 375`) with name/version/context as `-`, and the process exits with code 0

### Requirement: Text output reflects the Manager payload

In TEXT mode, the command SHALL render: (1) a headline panel with API name/version, manager id, revision id, ownership context (`type`/`group`/`owner`) when available, and the completeness score as a plain percentage (no classification band, color or bucket: the Manager payload does not classify — probing 25/09 confirmed the wire is `{completenessScore, suggestions[]}` only); (2) a progressive bar of 30 glyphs scaled to the score with a fixed gate marker at 70% and legend `(gate: ≥70%)`, plus `✖ −X.X pts` when below gate (headline-only mode when `--score-only`); (3) a numbered integral list of `suggestions[]` ordered by arrival index, with full-text word-wrap (no abbreviation, no invented columns). The command MUST NOT display severity, impact points, rule ids (SSD-xxx), dot-path `Where`, swagger ranges, derived classification or any collect-state (satellite status/source/note), because none of them exist in the Manager payload.

#### Scenario: Full text rendering
- **WHEN** the Manager returns `completenessScore: 70.5` and 12 suggestions
- **THEN** TEXT output shows the headline with `70.5%` (plain percentage, no Basic/Intermediate/Advanced label), the bar with gate marker, and a numbered list of all 12 suggestions integrally wrapped (no severity/impact/where columns)

#### Scenario: Score-only rendering
- **WHEN** user passes `--score-only`
- **WHEN** the Manager returns the completeness
- **THEN** output shows only the headline + bar + gate line, without the suggestions list

### Requirement: Versioned JSON contract apiops.sen-completeness/v1

The JSON output SHALL conform to the versioned contract `apiops.sen-completeness/v1` containing only proven fields: `schema`, `generatedAt`, `api{managerId, name|null, version|null, context{type, groupName, owner}|null}` (identity echoed for the blind stdout consumer; ownership context optional), `revision{managerId}`, `maturity{score}`, `gate{percent:70.0}` and `suggestions[]{index, text}`. There is NO collect-state block: the enrichment lookup SHALL NOT materialize status/source/note in the contract — degraded identity is expressed by the nulls alone. Fields that existed in the retired AG design (`violations`, `rulesLost`, `severity`, `impactPoints`, `range`, `classification`, `agCatalogId`, `agId`, `last`, `deployedEnvironments`) MUST be absent (never emitted as phantom nulls). YAML output SHALL serialize the same tree. No raw wire dumps are allowed in any output. Output MUST never contain tokens, cookies or credential material.

#### Scenario: JSON shape matches contract
- **WHEN** `-o json` is used with a successful Manager response
- **THEN** the parsed JSON conforms to the `apiops.sen-completeness/v1` tree described (contains `suggestions[].index/text`, contains no `violations`, no `severity`, no `classification`, no `ruleId`, no `satellite` keys)

#### Scenario: YAML mirrors JSON
- **WHEN** `-o yaml` is used
- **THEN** the YAML tree equals the JSON tree (same keys/values, serialized as YAML)

#### Scenario: Secrets never leak
- **WHEN** any successful or failing output is produced
- **THEN** stdout/stderr contain no token, cookie or credential blob

### Requirement: Exit code matrix

The command SHALL implement: pre-network input errors (`exit 1`); platform refusals on the Manager call (401, 403, 404 revision not found, 409/422 wrapped, exhausted 5xx) with honest PT-BR messages orienting next steps (`exit 2`); real emptiness and satellite failures (`exit 0`). For `404` specifically, the message SHALL orient `sen list api --id X --revisions` to rediscover a valid revision id. No stacktrace is ever shown; failures shall never abort mid-render leaving half-visible tables.

#### Scenario: Revision not found
- **WHEN** the Manager responds `404` for the informed revision
- **THEN** the CLI prints a PT-BR message suggesting `sen list api --id X --revisions` and exits with code 2

#### Scenario: Unauthorized
- **WHEN** the Manager responds `401` (session expired)
- **THEN** the CLI prints a PT-BR message orienting `sen login` and exits with code 2

#### Scenario: Success
- **WHEN** the Manager responds `200` with a valid payload
- **THEN** the command exits with code 0 regardless of the score value
