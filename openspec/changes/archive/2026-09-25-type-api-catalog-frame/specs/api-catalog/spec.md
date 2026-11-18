# Spec — api-catalog (delta)

## ADDED Requirements

### Requirement: Typed representation of the api-finder frame

The api-finder catalog frame SHALL be represented by domain models (`ApiCatalogEntry`, the aggregated `CatalogRevision`, `CatalogRevisionInfo` and the `OwnershipContext` enum), translated exclusively in the outbound adapter. A raw `Dict[str, Any]` of the finder wire MUST NOT cross the outbound→application boundary nor reach services, views or the CLI. Application services and the CLI SHALL access identity, revision and context data through the typed models (attributes/methods), never through loose dictionary keys.

#### Scenario: Adapter returns typed entries
- **WHEN** the adapter fetches the catalog/detail from the api-finder
- **THEN** callers receive `ApiCatalogEntry` instances (or `ApiCatalogPage.rows` of them), never raw dicts

#### Scenario: Services consume typed surface
- **WHEN** `ApiListingService` builds listing rows or derives drill-down cells
- **THEN** it operates on `ApiCatalogEntry`/`CatalogRevision` attributes and methods (no `dict.get` on wire keys inside service/domain/CLI)

#### Scenario: Ownership context is typed
- **WHEN** the finder reports `contextType` in any casing (e.g. `"ORGANIZATION"`, `" OrganiZation "`)
- **THEN** the adapter normalizes it to the matching `OwnershipContext` member; unknown/absent values degrade to `None`

### Requirement: Selado rules of the catalog revision

The revision aggregation SHALL preserve the sealed frame rules: frame blocks (`revisions`, `environments`, `completeness`, `wokflow` typo included) correlate implicitly by `apiRevision`; the completeness score takes the FIRST match and subsequent scores for the same revision are ignored; the workflow block follows LAST-match-wins; blocks with absent/unknown `apiRevision` are discarded. `lastRevision` arrives as the revision ID (object or scalar) and the revision NUMBER resolves by looking the ID up in `revisions[]`, never falling back to the ID itself.

#### Scenario: Sparse frame parses gracefully
- **WHEN** the finder returns a frame without `environments` and with `revisions: []`
- **THEN** the parsed entry survives (lists empty, optionals None) without raising

#### Scenario: Duplicate completeness score ignored
- **WHEN** `completeness[]` carries two scores for the same revision
- **THEN** only the first match populates `CatalogRevision.completenessScore`

#### Scenario: Last revision scalar resolves by id
- **WHEN** `lastRevision` is the scalar `88` and `revisions[]` maps id 88 → number 9
- **THEN** the entry exposes revision number 9; with id 99 (unmatched) it exposes None

### Requirement: Server-authoritative query and ordering

Listing SHALL delegate filtering and ordering to the api-finder: the adapter mounts `customSearch` (`apiName` OR `description`, with quote/parenthesys breaking characters stripped from user input), fixes `orderBy=apiId sort=asc`, and the response header `count` represents the FILTERED universe. Client-side visibility (r5 matrix) and window pagination remain application concerns. A window with negative `--offset` or non-positive `--limit` MUST be rejected before any network call.

#### Scenario: Query is forwarded server-side
- **WHEN** the service is invoked with a query
- **THEN** the port receives the query and the server answers with only matching rows (header `count` counts the matches)

#### Scenario: Invalid window fails fast
- **WHEN** a listing is requested with `--limit 0` or `--offset -1`
- **THEN** the service raises the corresponding `InvalidWindow` error without performing any request

### Requirement: Behavior-neutral migration for sen list

The refactor SHALL NOT change observable behavior of `sen list`: listing grid, drill-down grade, headlines, footers, messages and exit codes MUST remain identical. Rendering rules already sealed in the `sen-list` spec remain authoritative. The change adds structure only.

#### Scenario: Terminal output unchanged
- **WHEN** `sen list api` runs before and after the migration over the same fixture corpus
- **THEN** the rendered rows, headers, footers and exit codes are identical

#### Scenario: Legacy flows untouched
- **WHEN** the write-side flows (`publish`, conversor, `ApiPartialInfo`/`ApiFull`) are exercised
- **THEN** their models and contracts remain untouched by this change

### Requirement: Shared consumption surface for sibling commands

The typed frame SHALL be usable by sibling commands that need identity/context (starting with `sen completeness`): identity (`name`, `version`, ownership `contextType/contextGroupName/owner`) is readable from `ApiCatalogEntry` without any finder-specific key knowledge outside the adapter. This establishes the foundation referred to as "gatilho B2" in the archived `sen-list` design; the JSON channel itself remains out of scope.

#### Scenario: Completeness identity from typed entry
- **WHEN** `sen completeness` enriches its output with identity/context
- **THEN** it reads those values from `ApiCatalogEntry` fields (the retirement of loose lookups precedes its satellite integration)
