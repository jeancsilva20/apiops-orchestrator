## ADDED Requirements

### Requirement: Tenant without Adaptive Governance

Before evaluating the governance gate, the command SHALL check whether the Manager has the Adaptive Governance. When the tenant has no AG, the stage gates (allowed environments, completeness requirement and required attributes) SHALL NOT apply, the completeness SHALL NOT be read, and the `governance` block of the document SHALL carry `null` and empty lists, with no violations, keeping the contract version. When it is not possible to tell whether the AG is active, the command SHALL keep the current behavior.

#### Scenario: Deploy in a tenant without AG
- **WHEN** the attributes catalog of the AG answers 403 with the "Governance module enabled" message
- **THEN** the deployment proceeds without governance gates, no completeness call is made, and the text output shows no governance block
