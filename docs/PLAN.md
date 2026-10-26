# PermitsNJ implementation plan

## Inspection and scope

The initial checkout contained only Git metadata: no commits, source, schema, CI, or integrations. During implementation the user supplied three historical PermitsNJ guides: G-02 (2004), S-01 (2007), and S-02 (2009). They establish documented navigation, role/reference table dependencies and fee-schedule maintenance workflows. Their inventory and mapping are recorded in [REFERENCES.md](REFERENCES.md). No current source, database schema, complete UCC templates, S-A2 fee basis chart, municipal ordinance or live integration contract was supplied. Existing feature parity cannot be claimed. All people, addresses, municipalities, payments, and forms remain synthetic.

## Architecture

React + TypeScript + Vite frontend; same-origin FastAPI REST API; SQLite relational database with numbered SQL migrations, foreign keys, transactions, and integer cents. Passwords use salted scrypt, sessions use random opaque tokens stored as hashes, HttpOnly cookies and CSRF checks. A municipality-scoped admin, clerk, reviewer, inspector, and applicant demonstrate authorization. SQLite is appropriate for this single-instance demonstration; a reviewed PostgreSQL migration and operational controls are required before production scaling.

No external integrations or production credentials are available. Payments use a labeled mock provider; no card entry or real transactions. Certificates and notices are printable HTML documents, with CSV report exports. Arbitrary file uploads are deferred pending retention, malware scanning, and storage requirements.

## Proposed demonstration rules (not law)

- Permit assessments resolve the latest active, effective municipality/subcode schedule, with a building use-group variant where selected. The limited demonstration engine supports fixed/per-square-foot line items and line/schedule minima/maxima, not the documented full UCC tier/basis engine. Only explicit demo mode may fall back to building $150 + $0.25 per square foot, electrical $75, or plumbing $90; elevator/fire protection require a configured schedule. Non-demo operation has no invented rate fallback.
- Assessment amount and schedule ID are retained on the permit. Unrelated edits preserve the amount; changing type, area or use group, removing an exemption, or transferring to another municipality reassesses under the applicable current schedule. Fees cannot be reduced below payments already posted; issued/closed fees cannot be edited. Staff exemption requires a reason and cannot carry across a transfer.
- Default status graph: draft → submitted → under_review → approved → issued → closed. Submission requires prior approval; approval requires an approved plan review; issuance requires payment in full; closure requires a passed inspection. Administrators configure municipality-scoped graph overrides; checks on canonical approval/issuance/closure targets remain enforced.
- Applicants see and edit only their own draft applications and can submit and make mock payments. Staff have municipality-scoped access. Reviewers record plan reviews; inspectors record inspections; clerks/admins manage records and certificates/notices. Cross-municipality transfers require admin and an explicit destination; ownership and linked party records must remain valid in the destination.
- Payment requests require an idempotency key, reject overpayment, and atomically update history and audit. Mock declines never create successful payments. Reconciliation records a separate audited staff confirmation.
- A certificate requires an issued/closed permit, full payment, and a passed inspection. Revocation retains history. Notices require a deadline and track open/resolved status.

## Feature inventory and workflow mapping

All rows are requested new workflows; no pre-existing implementation was found.

| Area | Planned implementation | Acceptance evidence |
|---|---|---|
| Authentication and isolation | Sessions, CSRF, roles, municipality and applicant ownership scopes | Login/logout, permission and cross-tenant tests |
| Permits | Draft/create/edit/detail, search/sort/filter/page, guarded status changes, admin transfer | CRUD, invalid transitions and transfer tests |
| Directory | Municipality, applicant, contractor records | Validation and scoped API tests |
| Fees/payments | Explicit fee rules, exemptions, mock partial/full/declined payments, reconciliation | Exact cents, duplicate requests and balances tested |
| Plan reviews | Staff review and approval history | Role and issuance prerequisite tests |
| Inspections | Scheduling, inspector assignment, result and follow-up | Tenant and role checks, result tests |
| Certificates | Generate printable certificate, revoke and retain record | Preconditions and document authorization |
| Notices/orders | Issue, deadline, resolve and print | Lifecycle and document tests |
| Reports/audit | Date/municipality filters, summary, CSV, immutable audit records | Export and totals tests |
| UX/support | Responsive dashboard/navigation, accessible forms, empty/errors/loading, print and demo feedback | Build/type checks plus browser smoke tests |
| Historical reference tables | Show documented inventory and distinguish DCA-maintained inputs from municipality-maintained data | Inventory matches S-01 and identifies unavailable feeds |
| Historical fee maintenance | Partial demonstration schedule versions across five subcodes, copy, print/review, activation and effective-date fixed/per-unit assessment | API tests of version lifecycle, assessment, snapshots and tenant isolation; explicitly no UCC engine parity |

## Phases and acceptance criteria

1. Inspection and planning: publish this inventory, API contract and assumptions before implementation.
2. Vertical slice: authenticate → create permit → persistent list/detail → assess fee → mock partial payment; verify via real API tests before expanding.
3. Workflow expansion: plan review → inspection → issue/certificate; notices, directories, reports, transfers, audit and authorization. All important mutations transactional and tested.
4. UX integration: all requested navigation, usable forms/tables, permission-specific actions, explicit demo banner and recoverable errors. Production build and frontend checks pass.
5. Security/QA: run backend suites, lint/typecheck/build and browser smoke; diagnose defects, record gaps honestly.
6. Handoff: README, API reference, schema/migrations, environment example, deployment/backup guide, implementation matrix and limitations. Save repeatable cloud install/start instructions.

## Missing requirements and production risks

Current municipal fee ordinances, the full UCC line-item template, S-A1 worksheets and S-A2 fee-basis definitions, DCA reference/rate feeds, statutory approvals/forms, retention and accessibility policies, identity/SSO, cross-town transfer authority, payment/refund/chargeback rules, provider API, official certificate signatures, notification channels, document scanning/storage and hosting targets remain unspecified. The supplied guides are historical evidence, not a confirmation of current law or production requirements. Demo rules must not be interpreted as production policy. Production use needs independent security/legal review, TLS, identity lifecycle/MFA, backup restoration drills, approved payment provider, monitoring, and load testing. No real portal authentication, email, card processing, official government forms or external data exchange is represented as implemented.
