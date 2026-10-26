# Deployment, backup and recovery

## Supported demonstration topology

Build the React frontend, run one FastAPI service, and keep SQLite on persistent local storage. FastAPI serves `frontend/dist/`; all API and browser requests share an origin. A TLS-terminating reverse proxy should be the only public entry point. Do not expose the development Vite server as a production service.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
export DATABASE_PATH=/absolute/persistent/path/permitsnj.sqlite3
export DEMO_MODE=false
export SESSION_SECURE=true
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Use a service manager to restart the process, capture logs, and stop it cleanly. Set the working directory to the repository root. Restrict database and backup files to the service account. Keep configuration in the deployment platform's secure environment settings. The repository does not load `.env` automatically. Do not place secrets in command history, frontend build variables, source control, logs or browser storage.

This is not a turnkey production release. Identity lifecycle, MFA/SSO, statutory forms and fee schedules, approved payment integration, document storage/scanning and operational review are outstanding. A fresh non-demo database does not automatically create login accounts. Do not enable demo mode as a shortcut to provisioning real staff.

For deliberate local provisioning in a non-demo database, use the management CLI from the repository root with the same `DATABASE_PATH`. Password entry is interactive and must never be passed on the command line:

```bash
python -m backend.manage create-municipality --name "Example Municipality"
python -m backend.manage create-user --email staff@example.test --name "Example Administrator" --role admin --municipality-id 1
```

Use the municipality ID reported by the first command. This CLI supplies initial records, not a complete production identity lifecycle or an approval process. Access to the database and host is administrative access; restrict it accordingly.

## Before handling real information

- Approve municipal roles, transfer authority, status transitions, fees/exemptions, retention rules and official document wording with the responsible municipality.
- Use a reviewed identity onboarding/offboarding process, password recovery and MFA/SSO. Public demo passwords must never remain in a real-data database.
- Require HTTPS and `SESSION_SECURE=true`; limit proxy trust to the actual deployment. Validate host, proxy and session settings against the final topology. Avoid permissive CORS settings.
- Review all security controls and dependencies, run penetration and accessibility assessments, centralize access/security logs with retention controls, and add alerting and a shared rate limiter before multiple service instances.
- Integrate a supported payment provider using its tokenized/hosted flows and signed, idempotent webhooks. Never collect card numbers or security codes in this application. Refunds, chargebacks and true settlement reconciliation are not implemented.
- Review migration and concurrency requirements before replacing SQLite with PostgreSQL. SQLite and a single process are the delivered demonstration architecture; multi-replica deployment over a shared SQLite file is unsupported.

## Migration procedure

Migrations live in `backend/migrations/` and are applied during initialization. Before updating: stop writes, create and verify a backup, deploy the tested code and dependencies, start the backend, then verify health, login, read operations and a synthetic workflow in a staging environment. Do not edit a migration that has already been applied; add a new numbered migration. No automatic destructive down-migration is supplied.

## Consistent SQLite backups

Use SQLite's backup API rather than copying only the main file while WAL writes may be active. Run from an account authorized to read the database, storing backups outside the web root and repository:

```python
import sqlite3
from pathlib import Path

source = Path('/absolute/persistent/path/permitsnj.sqlite3')
target = Path('/secure/backup/location/permitsnj-YYYYMMDD.sqlite3')
with sqlite3.connect(source) as database, sqlite3.connect(target) as backup:
    database.backup(backup)
    assert backup.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
```

Encrypt backups at rest, restrict access, version them, and keep off-host copies. Choose backup frequency, retention, recovery point and recovery time objectives with the municipality. Include code version, configuration metadata and migration version in the operational record; keep secret values in the secret manager. Audit logs and sessions may contain sensitive operational information even without card data.

## Restore and drill

1. Stop the service and verify no writers remain. Preserve the failed database and all related journal/WAL files for diagnosis.
2. Restore a validated backup into a new file with correct ownership and permissions. Do not mix old WAL files with a replacement database.
3. Run `PRAGMA integrity_check` and `PRAGMA foreign_key_check` against the restored database. A successful restore must pass both, not merely create a file.
4. Point the matching application version at the restored file, start in a restricted staging environment, verify migration state and business record counts, and run scoped read/report checks.
5. Invalidate old sessions if compromise or rollback makes them unsafe, assess records written after the backup, then authorize reopening access. Record the elapsed recovery time and missing-data window.

A written procedure is not evidence of a tested disaster recovery process. Schedule a restore drill and document its results before production use.
