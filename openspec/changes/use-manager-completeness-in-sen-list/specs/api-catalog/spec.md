## MODIFIED Requirements

### Requirement: Selado rules of the catalog revision

The revision aggregation SHALL preserve the sealed frame rules: frame blocks (`revisions`, `environments`, `wokflow` typo included) correlate implicitly by `apiRevision`; the workflow block follows LAST-match-wins; blocks with absent/unknown `apiRevision` are discarded. The frame's `completeness[]` block MUST be ignored: its scores are stale relative to the Manager (21/10/2026 probe: 164 of 213 revisions diverged, in both directions, with no marker to tell stale values apart), so `CatalogRevision` carries no completeness reading. `lastRevision` arrives as the revision ID (object or scalar) and the revision NUMBER resolves by looking the ID up in `revisions[]`, never falling back to the ID itself. The only completeness source is the Manager endpoint `GET /api-manager/api/v3/revisions/{rid}/completeness`, read into `CatalogRevisionCompleteness{score, suggestions}`.

#### Scenario: Sparse frame parses gracefully
- **WHEN** the finder returns a frame without `environments` and with `revisions: []`
- **THEN** the parsed entry survives (lists empty, optionals None) without raising

#### Scenario: Duplicate completeness score ignored
- **WHEN** the finder frame carries `completeness[]` with one or more scores for the same revision (e.g. `[{score: 68.5, apiRevision: 10461}, {score: 70.0, apiRevision: 10461}]`)
- **THEN** the frame parses normally and every score is ignored: the revision 10461 exposes no completeness reading

#### Scenario: Last revision scalar resolves by id
- **WHEN** `lastRevision` is the scalar `88` and `revisions[]` maps id 88 → number 9
- **THEN** the entry exposes revision number 9; with id 99 (unmatched) it exposes None

#### Scenario: Same nested shape feeds teaser and mirror
- **WHEN** the frame reports `completeness=[{score: 66.8, apiRevision: 28541}]` and `GET /revisions/28541/completeness` returns `{completenessScore: 75.8, suggestions: [...]}`
- **THEN** both the drill-down teaser (`sen list api -r`) and the mirror (`sen completeness`) read the endpoint into `CatalogRevisionCompleteness` and show 75.8; the frame's 66.8 reaches neither
