# Quality assurance

The automated checks use synthetic data only. They do not call a payment processor, MyNewJersey, DCA, tax records, email services, or other external systems.

## Backend and frontend checks

From the repository root:

```sh
.venv/bin/python -m unittest discover -s backend/tests -v
cd frontend
npm run lint
npm run typecheck
npm run build
```

The final backend run passed 45 tests. The backend suites exercise actual HTTP routes against temporary SQLite databases: session/CSRF checks, role and municipality isolation, permit edits and status prerequisites, fee assessments/exemptions, payment retries/concurrency, inspection assignments/results, certificates/notices, fee-schedule versioning/activation, reports/CSV, and database constraints. The frontend checks validate lint rules, TypeScript, and a production build; those checks alone do not establish browser behavior.

## Real-browser smoke test

Build the frontend first, then run from the repository root:

```sh
.venv/bin/python tests/browser_smoke.py
```

Optional browser-test dependency, if unavailable in your Python environment:

```sh
.venv/bin/python -m pip install -r requirements-browser.txt
```

The script uses Chromium at `/usr/bin/chromium`. Install a trusted Chromium package for your operating system or set `CHROMIUM_PATH` to an existing compatible Chromium executable. Browser installation and operating-system dependencies are separate from the application dependencies. The test requires a Python environment with both the backend dependencies and Playwright installed.

The script starts its own local Uvicorn server on an available port and a new temporary SQLite database. It enables explicit demo mode, exercises the built frontend through Chromium, terminates the server, and deletes its database on exit. It leaves the regular development database unchanged. It prints a `PASS` line only after that group’s assertions complete and exits unsuccessfully if an assertion or browser operation fails.

The browser run passed all 11 assertion groups. The scenario checks:

1. Admin sign-in, populated dashboard, and a desktop render.
2. Create a building permit with 100 square feet; verify the declared demo fee is exactly $175. Edit its scope and verify existing applicant selection remains intact.
3. Submit and start review; verify premature approval displays a server error; record a plan review and approve.
4. Record a $50 partial mock payment, simulate a declined payment, recover with the remaining $125, and reconcile a payment.
5. Assign an inspector, record a passing result, issue the permit, generate a certificate, and open its authenticated printable document.
6. Create, open, and resolve a notice. Escape from a nested confirmation must preserve the permit dialog.
7. Verify case-insensitive partial search, status filters, and pagination.
8. Download a real CSV report and verify that it contains the created permit and financial columns.
9. View the reference-table inventory; create, print, review, and activate a synthetic elevator fee schedule.
10. Sign out and sign in as an applicant; verify the default dashboard, ownership of the staff-created permit, and hidden staff report navigation.
11. Use navigation at a 375-pixel viewport, check that the page body has no horizontal overflow, and assert no browser JavaScript exceptions occurred.

Successful runs save current screenshots at `/tmp/permitsnj-browser-desktop.png` and `/tmp/permitsnj-browser-mobile.png`. A failing run saves `/tmp/permitsnj-browser-failure.png`; the script removes an old failure screenshot before each run. Screenshots are local test artifacts, not published previews.

## Scope limits

This smoke test is one representative connected workflow. It does not replace the more extensive backend permission and failure tests, nor a formal accessibility audit, multi-browser/device testing, visual regression suite, load testing, penetration test, or user acceptance review. Browser print documents were opened and inspected; physical printers and PDF engine output were not verified. External integrations and the unsupported official fee bases remain unverified because they are not implemented.

The historical reference manuals establish some workflow requirements but do not establish current statutory compliance or full legacy feature parity. See [REFERENCES.md](REFERENCES.md) and [IMPLEMENTATION.md](IMPLEMENTATION.md) for the exact boundaries.
