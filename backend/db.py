"""SQLite persistence, numbered migrations and explicit synthetic demo fixtures."""

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


class Connection(sqlite3.Connection):
    """Transaction context that also closes the per-operation connection."""

    def __exit__(self, exc_type, exc, traceback):
        try:
            return super().__exit__(exc_type, exc, traceback)
        finally:
            self.close()


def connect():
    path = Path(os.getenv("DATABASE_PATH", "./data/permitsnj.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=15, factory=Connection)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=15000")
    return db


def initialize():
    with connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        for migration in sorted(Path(__file__).with_name("migrations").glob("*.sql")):
            if db.execute(
                "SELECT 1 FROM schema_migrations WHERE version=?", (migration.name,)
            ).fetchone():
                continue
            # One atomic transaction per migration including the version marker.
            script = (
                "BEGIN IMMEDIATE;\n"
                + migration.read_text()
                + "\nINSERT INTO schema_migrations VALUES ("
                + "'"
                + migration.name.replace("'", "''")
                + "',datetime('now'));\nCOMMIT;"
            )
            db.executescript(script)
        for row in [
            ("building", "Building", 15000, 25),
            ("electrical", "Electrical", 7500, 0),
            ("plumbing", "Plumbing", 9000, 0),
        ]:
            db.execute("INSERT OR IGNORE INTO permit_types VALUES (?,?,?,?)", row)
        codes = ["draft", "submitted", "under_review", "approved", "issued", "closed"]
        for index, code in enumerate(codes):
            following = codes[index + 1 : index + 2]
            db.execute(
                "INSERT OR IGNORE INTO statuses VALUES (?,?,?)",
                (code, code.replace("_", " ").title(), json.dumps(following)),
            )
    if os.getenv("DEMO_MODE", "").lower() == "true":
        seed_demo()


def seed_demo():
    from backend.security import hash_password

    timestamp = datetime.now(timezone.utc)
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
        db.executemany(
            "INSERT INTO municipalities VALUES (?,?)",
            [(1, "Maple Harbor (Demo)"), (2, "Cedar Borough (Demo)")],
        )
        roles = ["admin", "clerk", "reviewer", "inspector", "applicant"]
        password_hash = hash_password("DemoPermit2026!")
        for index, role in enumerate(roles, 1):
            db.execute(
                "INSERT INTO users VALUES (?,?,?,?,?,?)",
                (
                    index,
                    role.title() + " Demo",
                    role + "@demo.permitsnj.test",
                    password_hash,
                    role,
                    1,
                ),
            )
        db.execute(
            "INSERT INTO users VALUES (6,?,?,?,?,2)",
            ("Cedar Admin Demo", "other@demo.permitsnj.test", password_hash, "admin"),
        )
        applicants = [
            (1, 1, "Avery Sample", "applicant@demo.permitsnj.test", "555-0101"),
            (2, 1, "Jordan Example", "jordan@example.test", "555-0102"),
            (3, 1, "Riley Sample", "riley@example.test", "555-0103"),
            (4, 2, "Cedar Sample", "cedar@example.test", "555-0104"),
        ]
        db.executemany("INSERT INTO applicants VALUES (?,?,?,?,?)", applicants)
        db.executemany(
            "INSERT INTO contractors VALUES (?,?,?,?,?)",
            [
                (1, 1, "Harbor Works (Demo)", "DEMO-B001", "works@example.test"),
                (2, 1, "Maple Electric (Demo)", "DEMO-E002", "electric@example.test"),
                (3, 2, "Cedar Trades (Demo)", "DEMO-C003", "trades@example.test"),
            ],
        )
        samples = [
            ("building", "under_review", "Kitchen renovation", 120, True),
            ("electrical", "submitted", "Lighting replacement", 0, True),
            ("building", "draft", "Rear deck construction", 240, False),
            ("plumbing", "approved", "Bathroom fixtures", 0, True),
            ("building", "issued", "Accessible entrance", 80, True),
            ("electrical", "closed", "Panel replacement", 0, True),
            ("building", "submitted", "Home office addition", 360, True),
            ("plumbing", "under_review", "Water line replacement", 0, True),
            ("building", "draft", "Garden studio", 200, False),
            ("electrical", "approved", "EV charging equipment", 0, True),
            ("building", "submitted", "Porch repairs", 100, True),
            ("plumbing", "issued", "Utility sink installation", 0, True),
        ]
        rates = {"building": (15000, 25), "electrical": (7500, 0), "plumbing": (9000, 0)}
        for ident, (kind, status, description, area, prior) in enumerate(samples, 1):
            date = (timestamp - timedelta(days=ident)).isoformat()
            fee = rates[kind][0] + area * rates[kind][1]
            db.execute(
                "INSERT INTO permits(id,number,municipality_id,owner_id,applicant_id,contractor_id,type,status,description,work_address,area_sqft,prior_approval,fee_cents,created_at,updated_at) VALUES (?,?,1,5,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ident,
                    f"DEMO-2026-{ident:04d}",
                    (ident - 1) % 3 + 1,
                    2 if kind == "electrical" else 1,
                    kind,
                    status,
                    description,
                    f"{100 + ident} Example Lane",
                    area,
                    int(prior),
                    fee,
                    date,
                    date,
                ),
            )
            if status in ["approved", "issued", "closed"]:
                db.execute(
                    "INSERT INTO plan_reviews(permit_id,reviewer_id,result,notes,created_at) VALUES (?,3,?,?,?)",
                    (ident, "approved", "Synthetic demonstration review.", date),
                )
            if status in ["issued", "closed"]:
                db.execute(
                    "INSERT INTO payments(permit_id,amount_cents,method,reference,idempotency_key,request_hash,reconciled,created_at) VALUES (?,?,'mock',?,?,?,1,?)",
                    (ident, fee, f"MOCK-SEED-{ident}", f"seed-{ident}", "seed", date),
                )
                db.execute(
                    "INSERT INTO inspections(permit_id,inspector_id,scheduled_date,status,result,notes,created_at) VALUES (?,4,?,'completed','passed',?,?)",
                    (ident, date[:10], "Synthetic passed inspection.", date),
                )
            elif status == "under_review":
                db.execute(
                    "INSERT INTO inspections(permit_id,inspector_id,scheduled_date,status,created_at) VALUES (?,4,?,'scheduled',?)",
                    (ident, (timestamp + timedelta(days=ident)).date().isoformat(), date),
                )
        date = timestamp.isoformat()
        db.execute(
            "INSERT INTO permits(number,municipality_id,owner_id,applicant_id,contractor_id,type,status,description,work_address,area_sqft,prior_approval,fee_cents,created_at,updated_at) VALUES (?,2,6,4,3,'building','draft',?,?,0,0,15000,?,?)",
            ("DEMO-CEDAR-0001", "Synthetic Cedar project", "1 Cedar Example Road", date, date),
        )
        db.execute(
            "INSERT INTO notices(permit_id,kind,description,deadline,status,created_at) VALUES (1,'notice',?,?,'open',?)",
            (
                "Please supply the demonstration site plan.",
                (timestamp + timedelta(days=14)).date().isoformat(),
                date,
            ),
        )
