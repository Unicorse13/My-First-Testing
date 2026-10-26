# API reference

Base path: `/api`. Interactive OpenAPI documentation is available at `/docs` while the API is running. JSON names use `snake_case`; money is represented as integer cents. Errors return a `detail` field (validation errors may contain structured field details). Documents are HTML and reports support CSV.

## Authentication and request safety

- `POST /auth/login` accepts `{ "email": "...", "password": "..." }` and returns `{user, csrf_token, demo}`. The response sets an opaque `HttpOnly` session cookie. Never persist the password in browser storage.
- `GET /auth/me` returns the authenticated user and CSRF token.
- `POST /auth/logout` invalidates the current session.
- Protected requests require the session cookie. Mutating requests additionally require `X-CSRF-Token` with the session's token. Clients should retain the token in memory and fetch it again after page reload.
- `GET /health` is unauthenticated and checks service availability. It does not certify official workflows or external-provider availability.

Every protected endpoint applies server-side authorization. Municipality administrators remain municipality-scoped, apart from the explicit transfer operation. Applicants are restricted to their own permit records. Cross-scope record lookups return 404 to avoid disclosing existence.

## Configuration and directory records

| Method | Route | Purpose |
|---|---|---|
| GET | `/config` | Permit types, status definitions, available municipalities and same-municipality staff assignment metadata |
| GET | `/municipalities` | Municipality directory |
| GET, POST | `/applicants` | List/create applicant records |
| GET, POST | `/contractors` | List/create contractor records |
| GET, POST | `/statuses` | Read statuses; administrator writes configuration |
| GET | `/dashboard` | Permit count, open count, outstanding cents, inspections due and recent permits |

Applicant create payload: `{name,email,phone}`. Contractor payload: `{name,license_number,email}`. Status payload: `{code,label,next_statuses:[...]}`. Directory creation requires administrator/clerk authority; applicant users cannot provision arbitrary directory records. Applicant/contractor records are scoped to the current municipality; municipality names are reference data visible across municipalities. Linked records are validated on permit writes. Core demonstration status edges are protected; administrators can configure additional status definitions but cannot replace the guarded progression through this endpoint.

## Permits

| Method | Route | Body / result |
|---|---|---|
| GET | `/permits` | Paginated `{items,total,page,page_size}` |
| POST | `/permits` | `{applicant_id,contractor_id?,type,description,work_address,area_sqft,prior_approval}` |
| GET | `/permits/{id}` | Enriched permit plus reviews, inspections, payments, certificates, notices and audit |
| PATCH | `/permits/{id}` | Editable subset of creation fields |
| POST | `/permits/{id}/status` | `{status}`; validated transition and prerequisites |
| POST | `/permits/{id}/exemption` | `{exempt,reason}`; authorized staff only |
| POST | `/permits/{id}/transfer` | `{municipality_id,applicant_id,contractor_id?}`; administrator only |

List query parameters: `q`, `status`, `type`, `sort`, `direction`, `page`, `page_size`. Search is case-insensitive and partial. Sort fields are allowlisted. Permit records include `fee_cents`, `paid_cents`, `balance_cents`, applicant/contractor names and municipality name. Editable application changes recalculate the demonstration fee; a changed fee cannot fall below posted payments. Applicants can edit only their own drafts. Staff can edit drafts, submitted applications and applications under review. Issued/closed records cannot be edited through this endpoint.

Transfer is restricted to draft/submitted applications without payments, plan reviews or inspections. Destination parties must belong to the destination municipality. Transfer resets the permit to draft and clears prior approval, and records source/destination audit entries. The destination must have a provisioned owner. This deliberately narrow demonstration transfer does not establish a legal process for moving issued permits across municipalities.

Demonstration fees: building $150 + $0.25 per square foot; electrical $75; plumbing $90. A staff exemption requires a reason. Status progression defaults to draft → submitted → under_review → approved → issued → closed. Submission requires prior approval; approval requires an approved review; issuance requires payment in full; closure requires a passed inspection. These are application sample policies, not statutory requirements.

## Payments and workflow records

| Method | Route | Body / result |
|---|---|---|
| GET | `/payments` | Scoped payment history |
| POST | `/permits/{id}/payments` | `{amount_cents,idempotency_key,simulate_failure?}` |
| POST | `/payments/{id}/reconcile` | Staff confirms reconciliation |
| GET | `/plan-reviews` | Scoped review history |
| POST | `/permits/{id}/plan-reviews` | `{result:"approved"|"changes_requested",notes}` |
| GET | `/inspections` | Scoped inspection schedule and results |
| POST | `/permits/{id}/inspections` | `{inspector_id,scheduled_date}` |
| PATCH | `/inspections/{id}` | `{result:"passed"|"failed",notes,follow_up}` |
| GET | `/certificates` | Scoped certificate history |
| POST | `/permits/{id}/certificates` | Generate certificate after prerequisites |
| POST | `/certificates/{id}/revoke` | Revoke without deleting history |
| GET | `/certificates/{id}/document` | Authorized, printable HTML |
| GET | `/notices` | Scoped notice/order history |
| POST | `/permits/{id}/notices` | `{kind:"notice"|"order",description,deadline}` |
| PATCH | `/notices/{id}` | `{status:"resolved"}` |
| GET | `/notices/{id}/document` | Authorized, printable HTML |

Payment provider is **mock only**. Successful first payment returns 201 and a replay returns 200. Reusing a key with a different request is rejected. Overpayments, nonpositive amounts and simulated declines fail without posting a successful payment. Requests, payment insertion and financial audit use a database transaction. Reconciliation is a demonstration bookkeeping confirmation, not a bank or processor settlement match.

Reviewers/admins record plan reviews. Clerks/admins schedule inspections; the assigned inspector/admin records the result. Clerks/admins handle reconciliation, notices and certificates. An issued/closed permit, full payment and a passed inspection are required for a certificate. Sensitive operations retain audit history.

## Reports and audit

- `GET /reports?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&municipality_id=...` returns `{summary:{permit_count,assessed_cents,paid_cents,balance_cents},items:[...]}`.
- `GET /reports/export` accepts the same filters and returns CSV. Text is escaped for spreadsheet safety.
- `GET /audit` returns recent scoped audit entries for staff.

Date filters are report selection criteria; they do not turn permit totals into provider settlement statements. A municipality filter cannot widen the user's authority. No raw payment card information, email sending or external government service is supported.

## Historical reference and partial fee maintenance

These endpoints preserve a limited subset of the historical S-01/S-02 maintenance workflow. They do not reproduce UCC basis/tier mathematics, official state rates or MyNewJersey integration. See [the complete reference mapping](REFERENCES.md).

| Method | Route | Purpose |
|---|---|---|
| GET | `/reference-tables` | Staff inventory identifying incomplete reference-table support |
| GET, POST | `/fee-schedules` | List/create municipality-scoped schedule versions |
| GET, PATCH | `/fee-schedules/{id}` | Read schedule / edit draft metadata |
| POST | `/fee-schedules/{id}/items` | Append an ordered demonstration line item |
| PATCH | `/fee-schedules/{id}/items/{position}` | Edit an existing line without reordering |
| POST | `/fee-schedules/{id}/copy` | Create a new draft with `{effective_date}` |
| POST | `/fee-schedules/{id}/activate` | Administrator review confirmation `{confirmed_review:true}` |
| GET | `/fee-schedules/{id}/document` | Authorized printable HTML schedule |

Five subcodes are available: building, electrical, elevator, fire protection and plumbing. Building schedules can retain a use-group label. Schedule metadata includes effective date, ordinance citation and optional minimum/maximum cents. Demonstration line bases are restricted to `fixed` and `per_unit`, with integer-cent amounts and optional line minima. Authoritative UCC line items, S-A2 basis definitions, tier/range/group calculation and state-rate percentages are unavailable. Active versions are immutable; copy to a new effective-date draft before amendment. Clerks/admins maintain drafts; only admins activate. Staff reads and writes remain municipality-scoped.
