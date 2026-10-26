# PermitsNJ implementation plan

## Inspection and scope

The initial checkout contains only Git metadata: no commits, source, schema, screenshots, business rules, CI, or integrations. No existing feature parity can be claimed. This is a new demonstration implementation, not a verified New Jersey regulatory system. All people, addresses, municipalities, payments, and forms are synthetic.

## Architecture

React + TypeScript + Vite frontend; same-origin FastAPI REST API; SQLite relational database with numbered SQL migrations, foreign keys, transactions, and integer cents. Passwords use salted scrypt, sessions use random opaque tokens stored as hashes, HttpOnly cookies and CSRF checks. A municipality-scoped admin, clerk, reviewer, inspector, and applicant demonstrate authorization. SQLite is appropriate for this single-instance demonstration; a reviewed PostgreSQL migration and operational controls are required before production scaling.

No external integrations or production credentials are available. Payments use a labeled mock provider; no card entry or real transactions. Certificates and notices are printable HTML documents, with CSV report exports. Arbitrary file uploads are deferred pending retention, malware scanning, and storage requirements.

## Proposed demonstration rules (not law)

- Building fee: $150 + $0.25 per square foot; electrical $75; plumbing $90. Explicit staff exemption requires a reason. Historical assessed fees remain fixed until staff explicitly reassess.
- Status graph: draft → submitted → under_review → approved → issued → closed. Submission requires prior approval; approval requires an approved plan review; issuance requires payment in full; closure requires a passed inspection. Status definitions are stored as configuration data. Only admins change the graph.
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

## Phases and acceptance criteria

1. Inspection and planning: publish this inventory, API contract and assumptions before implementation.
2. Vertical slice: authenticate → create permit → persistent list/detail → assess fee → mock partial payment; verify via real API tests before expanding.
3. Workflow expansion: plan review → inspection → issue/certificate; notices, directories, reports, transfers, audit and authorization. All important mutations transactional and tested.
4. UX integration: all requested navigation, usable forms/tables, permission-specific actions, explicit demo banner and recoverable errors. Production build and frontend checks pass.
5. Security/QA: run backend suites, lint/typecheck/build and browser smoke; diagnose defects, record gaps honestly.
6. Handoff: README, API reference, schema/migrations, environment example, deployment/backup guide, implementation matrix and limitations. Save repeatable cloud install/start instructions.

## Missing requirements and production risks

Municipal fee schedules, statutory approvals/forms, retention and accessibility policies, identity/SSO, staff provisioning, cross-town transfer authority, payment/refund/chargeback rules, provider API, official certificate signatures, notification channels, document scanning/storage and hosting targets remain unspecified. Demo rules must not be interpreted as production policy. Production use needs independent security/legal review, TLS, identity lifecycle/MFA, backup restoration drills, approved payment provider, monitoring, and load testing. No real email, card processing, official government forms or external data exchange is represented as implemented.
