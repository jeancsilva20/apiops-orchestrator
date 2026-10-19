# api-catalog (delta) — add-sen-completeness

## MODIFIED Requirements

### Requirement: Selado rules of the catalog revision

The revision aggregation SHALL preserve the sealed frame rules: frame blocks (`revisions`, `environments`, `completeness`, `wokflow` typo included) correlate implicitly by `apiRevision`; the completeness score takes the FIRST match and subsequent scores for the same revision are ignored; the workflow block follows LAST-match-wins; blocks with absent/unknown `apiRevision` are discarded. `lastRevision` arrives as the revision ID (object or scalar) and the revision NUMBER resolves by looking the ID up in `revisions[]`, never falling back to the ID itself. The completeness reading lives as a NESTED object on the revision: the flat `completenessScore` field is RETIRED in favor of `CatalogRevision.completeness` (`CatalogRevisionCompleteness{score, suggestions}`). The catalog frame populates the nested object with the score only (the frame carries no suggestions); the completeness ENDPOINT (`GET /api-manager/api/v3/revisions/{rid}/completeness`) populates the SAME object with score + suggestions.

#### Scenario: Sparse frame parses gracefully
- **WHEN** the finder returns a frame without `environments` and with `revisions: []`
- **THEN** the parsed entry survives (lists empty, optionals None) without raising

#### Scenario: Duplicate completeness score ignored
- **WHEN** `completeness[]` carries two scores for the same revision
- **THEN** only the first match populates `CatalogRevision.completeness.score` (nested object; the flat `completenessScore` no longer exists)

#### Scenario: Last revision scalar resolves by id
- **WHEN** `lastRevision` is the scalar `88` and `revisions[]` maps id 88 → number 9
- **THEN** the entry exposes revision number 9; with id 99 (unmatched) it exposes None

#### Scenario: Same nested shape feeds teaser and mirror
- **WHEN** the catalog frame populates `completeness={score: 70.5}` and, separately, the endpoint `GET /revisions/{rid}/completeness` returns `{completenessScore: 70.5, suggestions: [...]}`
- **THEN** both land on the same `CatalogRevisionCompleteness` object shape (teaser: score only; mirror: score + suggestions)
