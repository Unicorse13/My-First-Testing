# Scope, assumptions and remaining work

This file describes the delivery boundary. The initial repository was empty. Three historical guides supplied during implementation document navigation, reference data and fee-maintenance workflows; [REFERENCES.md](REFERENCES.md) maps those requirements to the demonstration and its gaps. No original source, database schema or integration contract was provided. `PLAN.md` records proposed behavior and acceptance criteria. Delivered test output is the authority for what was verified; planned items are not evidence that an implementation works.

## Demonstration behavior

- React/TypeScript interface, FastAPI API, SQLite migrations and persistent records.
- Municipality-scoped staff roles and applicant ownership; password/session authentication with CSRF protection.
- Permit drafts, edits, workflow progression, directory records, fee calculation and explicit exemptions.
- Mock partial/full payments, safe request retries, declines and staff reconciliation confirmation.
- Plan review history, inspection scheduling/results/follow-up, certificate generation/revocation, notices/orders and deadlines.
- Printable demonstration documents, report summaries/CSV exports and important-operation audit history.

Exact UI coverage, automated results and any remaining implementation gaps must be reviewed in the final handoff. In particular, a passing API test is distinct from a manually verified browser interaction.

## Explicit assumptions

Fees, transitions and prerequisite checks are illustrative and centralized in application configuration. Municipality records, users, addresses and contact details are synthetic. Staff are scoped to one municipality; an explicit administrator transfer is the sole cross-municipality write workflow. A reviewer does not automatically have clerk or inspector authority. Applicant access is limited by authenticated record ownership, not a supplied applicant identifier.

Payment reconciliation means a staff confirmation in this demonstration. No provider settlement data is available. Certificates and notices are HTML demonstration documents with a print workflow; they are not digitally signed official forms. CSV reports describe stored permit records and posted mock payments.

## Incomplete or external dependencies

| Area | Remaining requirement |
|---|---|
| Existing-system parity | Historical G-02/S-01/S-02 guides were supplied. Original source/schema, remaining workflow guides and current requirements are needed to assess parity. |
| Reference-table administration | Architects/engineers, block/lot, use groups, official staffing, interlocal/state offices, inspection types, third-party agencies and DCA-maintained tables are inventoried; their full maintenance/import workflows are not implemented. |
| Fee schedule engine | Partial version maintenance is separate from sample permit calculation. Full UCC templates, S-A2 basis chart, tier/group math, use-group variants, official DCA rates and ordinance validation remain unavailable. |
| Portal authentication | MyNewJersey registration, authentication codes and role-manager integration documented by G-02 have no supplied API/credentials and are not integrated. |
| Statutory rules | Confirm NJ/municipal fee schedules, permit types, approvals, exemptions, notices, certificate wording and retention. |
| Configuration | Core demo status transitions are protected; custom status records are available, but arbitrary replacement of the guarded workflow and a municipality-specific rule administration UI remain outside this delivery. |
| Transfers | Only unpaid draft/submitted records without reviews or inspections can transfer; moving issued permits and their official history requires approved rules. |
| Production authentication | Approved staff provisioning/deprovisioning, password recovery, MFA/SSO and organizational policy. |
| Payments | Approved provider/API credentials, signed webhook handling, refunds, chargebacks and settlement reconciliation. No real transactions. |
| Documents | File uploads, private object storage, malware scanning, retention/legal hold and official signatures. Only generated documents are supported. |
| Notifications | Email/SMS delivery, provider credentials, consent and delivery tracking. No external messages are sent. |
| Government integrations | Published API contracts, permitted data access and secure credentials. None are fabricated. |
| Operations | Production hosting, monitoring/alerting, centralized rate limiting, load/security testing and validated backup restoration. |
| Accessibility | Manual keyboard/screen reader and mobile-device acceptance testing against the required standard. Automated/build checks alone do not prove compliance. |

No production credentials or personal, financial or government records are included. Use synthetic data only until the production requirements and reviews are resolved.
