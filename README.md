# PermitsNJ

A full-stack **demonstration** of municipal permit management. React/TypeScript runs against a same-origin FastAPI API and persistent SQLite database. Every seeded person, municipality, property, payment and document is fictional. Fees and workflow rules are illustrative, not New Jersey legal requirements. Three historical user/setup guides supplied during implementation inform the [reference inventory](docs/REFERENCES.md); no legacy source or database schema was supplied, and existing-system feature parity is not claimed.

See [implementation scope and limitations](docs/IMPLEMENTATION.md), [reference-to-implementation mapping](docs/REFERENCES.md), [API reference](docs/API.md), [deployment and recovery](docs/DEPLOYMENT.md), and the [architecture and acceptance plan](docs/PLAN.md).

## Try it in a browser (no Windows installation)

Open [the GitHub project](https://github.com/Unicorse13/My-First-Testing), select **Code → Codespaces → Create codespace on main**, and wait for the automatic setup. The app should open automatically; otherwise use **Ports → 8000 → Open in Browser**. Click **Enter demo workspace** to sign in. See [the browser guide](docs/TRY-DEMO.md) for details. Codespaces access and usage allowance are required.

## Local setup

Prerequisites: Python 3.12+, Node.js 22.12+ and npm. Commands below run from the repository root.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
cd frontend
npm ci
npm run build
cd ..
export DEMO_MODE=true
export SESSION_SECURE=false
export DATABASE_PATH=./data/permitsnj.sqlite3
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open the application's port 8000 using your development platform's supported port forwarding. The backend serves the production frontend build. If forwarding uses a hostname other than `localhost` or `127.0.0.1`, add that exact hostname to comma-separated `ALLOWED_HOSTS` before startup. Do not use a wildcard for a public deployment. The first demo startup applies migrations and creates synthetic records; subsequent starts reuse the database. `.env.example` documents settings; the backend does not automatically load `.env` files. The `data/` directory and local configuration are ignored by Git. Do not commit database files or secrets.

For frontend hot reload, keep the backend running and run `npm run dev -- --host 0.0.0.0` from `frontend/`. Vite proxies `/api` requests to backend port 8000. Use the same browser origin throughout a session.

## Demonstration accounts

Local demo mode enables the following accounts, all using password `DemoPermit2026!`:

| Email | Role | Municipality |
|---|---|---|
| `admin@demo.permitsnj.test` | Administrator | Maple Harbor (Demo) |
| `clerk@demo.permitsnj.test` | Clerk | Maple Harbor (Demo) |
| `reviewer@demo.permitsnj.test` | Plan reviewer | Maple Harbor (Demo) |
| `inspector@demo.permitsnj.test` | Inspector | Maple Harbor (Demo) |
| `applicant@demo.permitsnj.test` | Applicant | Maple Harbor (Demo) |
| `other@demo.permitsnj.test` | Administrator | Cedar Borough (Demo) |

These credentials are public and unsuitable for a publicly accessible service containing real data. `DEMO_MODE` defaults to false; local insecure cookies require explicitly setting `SESSION_SECURE=false`. Production must use secure cookies over HTTPS and a database that has never been seeded with demo accounts.

## Demonstration walkthrough

1. Sign in as the administrator, open **Permits**, and create a draft using a synthetic applicant and work site.
2. Review the explicit calculated fee. Record prior approval before submitting; advance the permit into review.
3. Record an approved plan review, then approve the permit.
4. Make a **mock** partial payment and observe the remaining balance. Finish the balance with another mock payment. Payment requests have idempotency keys so safe retries do not double charge.
5. Schedule an inspection and record its result. Issue the permit once paid, then generate a printable demonstration certificate after a passed inspection.
6. Create a notice or order, set its deadline, and resolve it. Inspect the history and export a filtered report as CSV.
7. Sign in with the second municipality account or applicant account to inspect the restricted views. Municipal isolation and applicant ownership are enforced by the API, not only the interface.

No card fields or real transaction endpoints exist. Payment failures can be simulated. Exported certificates and notices are unverified demonstration forms and do not confer official approval.

## Checks

```bash
. .venv/bin/activate
ruff check backend
ruff format --check backend
python -m unittest discover -s backend/tests -v
cd frontend
npm run typecheck
npm run lint
npm run build
```

Backend dependencies are pinned through `constraints.txt`; frontend dependencies use `package-lock.json`. GitHub Actions runs backend checks and the frontend production build when these commits are pushed. The workflow has been added but has not been executed on GitHub.

See [browser test instructions and verification results](docs/QA.md) for the optional Playwright suite.

Backend tests create temporary databases and exercise API behavior. The test command must report actual executed tests; a zero-test result is not validation. Frontend checks establish code/build health; they do not substitute for browser, accessibility or municipal acceptance testing. Refer to the delivered verification report for the checks actually run.

## Data and configuration

Numbered SQL files in `backend/migrations/` define the relational schema. Migration application is recorded in the database during backend initialization. Keep the database on persistent storage and back it up before deployment or migration. Fee amounts use integer cents; no floating-point currency is stored. Activated effective fee schedules support a limited fixed/per-square-foot calculation with minima/maxima and optional building use-group variants. The permit retains its assessed amount and schedule ID; activating a later version does not silently change historical assessments. Only explicit demo mode supplies fallback building/electrical/plumbing sample fees; elevator/fire protection and non-demo assessments require a matching schedule. No full UCC tier/basis engine is claimed.

Sessions use opaque cookies; passwords are salted scrypt hashes. Non-demo startup rejects a database containing the public demo accounts; use a separate clean database when provisioning real users. Do not copy demo credentials or settings into production deployment configuration.

Each cloud task already has an isolated checkout; use that checkout rather than creating Git worktrees unless specifically requested. Install dependencies from the lockfile and start processes afresh when a cloud environment is restored; live servers are not part of its filesystem snapshot.
