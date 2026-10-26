"""Integration tests use isolated SQLite databases and actual FastAPI requests."""

import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": self.directory.name + "/test.sqlite3",
                "DEMO_MODE": "true",
                "SESSION_SECURE": "false",
            },
        )
        self.environment.start()
        from backend.main import _attempts, app

        _attempts.clear()
        self.client = TestClient(app)
        self.client.__enter__()
        self.login()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.environment.stop()
        self.directory.cleanup()

    def login(self, role="admin"):
        self.client.headers.pop("X-CSRF-Token", None)
        result = self.client.post(
            "/api/auth/login",
            json={"email": role + "@demo.permitsnj.test", "password": "DemoPermit2026!"},
        )
        self.assertEqual(result.status_code, 200, result.text)
        self.client.headers["X-CSRF-Token"] = result.json()["csrf_token"]

    def post(self, url, body=None):
        return self.client.post("/api" + url, json=body or {})

    def test_partial_payment_replay_balance_and_reconcile(self):
        first = self.post(
            "/permits/1/payments", {"amount_cents": 2000, "idempotency_key": "partial-payment-001"}
        )
        self.assertEqual(first.status_code, 201, first.text)
        self.assertNotIn("request_hash", first.json())
        self.assertNotIn("idempotency_key", first.json())
        again = self.post(
            "/permits/1/payments", {"amount_cents": 2000, "idempotency_key": "partial-payment-001"}
        )
        self.assertEqual(again.status_code, 200)
        self.assertEqual(first.json()["id"], again.json()["id"])
        permit = self.client.get("/api/permits/1").json()
        self.assertEqual(permit["paid_cents"], 2000)
        self.assertEqual(permit["balance_cents"], 16000)
        final = self.post(
            "/permits/1/payments",
            {"amount_cents": 16000, "idempotency_key": "remaining-payment-001"},
        )
        self.assertEqual(final.status_code, 201)
        self.assertEqual(self.client.get("/api/permits/1").json()["balance_cents"], 0)
        payment = self.post("/payments/" + str(first.json()["id"]) + "/reconcile")
        self.assertEqual(payment.status_code, 200)
        self.assertEqual(payment.json()["reconciled"], 1)
        actions = [row["action"] for row in self.client.get("/api/audit").json()]
        self.assertIn("payment_reconciled", actions)

    def test_overpayment_invalid_amount_and_key_conflict(self):
        self.assertEqual(
            self.post(
                "/permits/1/payments",
                {"amount_cents": 999999, "idempotency_key": "overpayment-001"},
            ).status_code,
            409,
        )
        for amount in [-1, 0, 1.4, "100"]:
            self.assertEqual(
                self.post(
                    "/permits/1/payments",
                    {"amount_cents": amount, "idempotency_key": "invalid-payment-001"},
                ).status_code,
                422,
            )
        self.assertEqual(
            self.post(
                "/permits/1/payments",
                {"amount_cents": 100, "idempotency_key": "conflicting-payment-001"},
            ).status_code,
            201,
        )
        self.assertEqual(
            self.post(
                "/permits/1/payments",
                {"amount_cents": 200, "idempotency_key": "conflicting-payment-001"},
            ).status_code,
            409,
        )
        self.assertEqual(
            self.post(
                "/permits/2/payments",
                {"amount_cents": 100, "idempotency_key": "conflicting-payment-001"},
            ).status_code,
            409,
        )

    def test_decline_does_not_change_balance(self):
        result = self.post(
            "/permits/1/payments",
            {"amount_cents": 100, "idempotency_key": "mock-decline-001", "simulate_failure": True},
        )
        self.assertEqual(result.status_code, 402)
        self.assertEqual(self.client.get("/api/permits/1").json()["paid_cents"], 0)
        self.assertIn(
            "payment_declined", [row["action"] for row in self.client.get("/api/audit").json()]
        )

    def test_payment_concurrency_serializes(self):
        from concurrent.futures import ThreadPoolExecutor

        def pay(key):
            return self.post(
                "/permits/2/payments", {"amount_cents": 7500, "idempotency_key": key}
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(pay, ["concurrent-payment-1", "concurrent-payment-2"]))
        self.assertEqual(sorted(outcomes), [201, 409])
        self.assertEqual(self.client.get("/api/permits/2").json()["paid_cents"], 7500)

    def test_plan_reviews_roles_and_validation(self):
        self.login("clerk")
        self.assertEqual(
            self.post(
                "/permits/1/plan-reviews", {"result": "approved", "notes": "Checked demo plans."}
            ).status_code,
            403,
        )
        self.login("reviewer")
        good = self.post(
            "/permits/1/plan-reviews",
            {"result": "changes_requested", "notes": "Provide synthetic structural detail."},
        )
        self.assertEqual(good.status_code, 201, good.text)
        self.assertEqual(
            self.post("/permits/1/plan-reviews", {"result": "approved", "notes": " "}).status_code,
            422,
        )
        self.assertEqual(
            self.post(
                "/permits/3/plan-reviews", {"result": "approved", "notes": "Cannot review draft."}
            ).status_code,
            409,
        )
        self.assertEqual(
            self.post(
                "/permits/13/plan-reviews", {"result": "approved", "notes": "Cross town."}
            ).status_code,
            404,
        )

    def test_inspection_schedule_results_and_followup(self):
        schedule = self.post(
            "/permits/2/inspections",
            {"inspector_id": 4, "scheduled_date": (date.today() + timedelta(days=2)).isoformat()},
        )
        self.assertEqual(schedule.status_code, 201, schedule.text)
        ident = schedule.json()["id"]
        self.login("inspector")
        url = "/api/inspections/" + str(ident)
        self.assertEqual(
            self.client.patch(url, json={"result": "failed", "notes": "Needs repair."}).status_code,
            422,
        )
        done = self.client.patch(
            url,
            json={
                "result": "failed",
                "notes": "Needs repair.",
                "follow_up": "Schedule repeat inspection after repair.",
            },
        )
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual(done.json()["status"], "completed")
        self.assertEqual(
            self.client.patch(
                url, json={"result": "passed", "notes": "Trying to overwrite."}
            ).status_code,
            409,
        )

    def test_inspection_assignment_and_dates(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.assertEqual(
            self.post(
                "/permits/2/inspections", {"inspector_id": 6, "scheduled_date": tomorrow}
            ).status_code,
            422,
        )
        self.assertEqual(
            self.post(
                "/permits/2/inspections", {"inspector_id": 4, "scheduled_date": "2020-01-01"}
            ).status_code,
            422,
        )
        self.assertEqual(
            self.post(
                "/permits/3/inspections", {"inspector_id": 4, "scheduled_date": tomorrow}
            ).status_code,
            409,
        )
        scheduled = self.post(
            "/permits/2/inspections", {"inspector_id": 4, "scheduled_date": tomorrow}
        )
        self.assertEqual(scheduled.status_code, 201)
        self.assertEqual(
            self.post(
                "/permits/2/inspections", {"inspector_id": 4, "scheduled_date": tomorrow}
            ).status_code,
            409,
        )
        from backend.db import connect

        with connect() as db:
            db.execute(
                "INSERT INTO users(id,name,email,password_hash,role,municipality_id) VALUES (20,'Other inspector','second@example.test','unused','inspector',1)"
            )
            db.execute(
                "UPDATE inspections SET inspector_id=20 WHERE id=?", (scheduled.json()["id"],)
            )
        self.login("inspector")
        self.assertEqual(
            self.client.patch(
                "/api/inspections/" + str(scheduled.json()["id"]),
                json={"result": "passed", "notes": "Not assigned."},
            ).status_code,
            403,
        )

    def test_certificate_lifecycle_document_and_guards(self):
        self.assertEqual(self.post("/permits/1/certificates").status_code, 409)
        issued = self.post("/permits/5/certificates")
        self.assertEqual(issued.status_code, 201, issued.text)
        ident = issued.json()["id"]
        self.assertEqual(self.post("/permits/5/certificates").status_code, 409)
        document = self.client.get("/api/certificates/" + str(ident) + "/document")
        self.assertEqual(document.status_code, 200)
        self.assertIn("DEMONSTRATION ONLY", document.text)
        self.assertIn("DEMO-2026-0005", document.text)
        self.assertIn("no-store", document.headers["cache-control"])
        self.assertEqual(
            self.post("/certificates/" + str(ident) + "/revoke").json()["status"], "revoked"
        )
        self.assertIn(
            "revoked", self.client.get("/api/certificates/" + str(ident) + "/document").text
        )
        self.assertEqual(self.post("/permits/5/certificates").status_code, 201)

    def test_pending_inspection_blocks_certificate(self):
        scheduled = self.post(
            "/permits/5/inspections",
            {"inspector_id": 4, "scheduled_date": date.today().isoformat()},
        )
        self.assertEqual(scheduled.status_code, 201)
        self.assertEqual(self.post("/permits/5/certificates").status_code, 409)
        completed = self.client.patch(
            "/api/inspections/" + str(scheduled.json()["id"]),
            json={"result": "passed", "notes": "Follow-up passed."},
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(self.post("/permits/5/certificates").status_code, 201)

    def test_notice_lifecycle_html_safety_and_authorization(self):
        notice = self.post(
            "/permits/1/notices",
            {
                "kind": "order",
                "description": "<script>alert(1)</script>",
                "deadline": (date.today() + timedelta(days=3)).isoformat(),
            },
        )
        self.assertEqual(notice.status_code, 201, notice.text)
        ident = notice.json()["id"]
        document = self.client.get("/api/notices/" + str(ident) + "/document")
        self.assertIn("&lt;script&gt;", document.text)
        self.assertNotIn("<script>", document.text)
        resolved = self.client.patch("/api/notices/" + str(ident), json={"status": "resolved"})
        self.assertEqual(resolved.json()["status"], "resolved")
        self.login("other")
        self.assertEqual(
            self.client.get("/api/notices/" + str(ident) + "/document").status_code, 404
        )
        self.assertEqual(
            self.client.patch(
                "/api/notices/" + str(ident), json={"status": "resolved"}
            ).status_code,
            404,
        )

    def test_scoped_lists_and_applicant_permissions(self):
        for endpoint in ["payments", "plan-reviews", "inspections", "certificates", "notices"]:
            result = self.client.get("/api/" + endpoint)
            self.assertEqual(result.status_code, 200, result.text)
            self.assertTrue(all(row["permit_id"] != 13 for row in result.json()))
        self.login("applicant")
        self.assertEqual(
            self.post(
                "/permits/1/notices",
                {
                    "kind": "notice",
                    "description": "Forbidden.",
                    "deadline": date.today().isoformat(),
                },
            ).status_code,
            403,
        )
        self.assertEqual(self.post("/permits/5/certificates").status_code, 403)
        self.assertEqual(self.client.get("/api/reports").status_code, 403)
        self.assertEqual(self.client.get("/api/audit").status_code, 403)
        self.assertEqual(
            self.post(
                "/permits/13/payments",
                {"amount_cents": 100, "idempotency_key": "cross-town-payment"},
            ).status_code,
            404,
        )

    def test_reports_filters_summary_and_csv(self):
        report = self.client.get("/api/reports").json()
        self.assertEqual(report["summary"]["permit_count"], 12)
        self.assertEqual(
            report["summary"]["assessed_cents"], sum(row["fee_cents"] for row in report["items"])
        )
        self.assertEqual(
            report["summary"]["balance_cents"],
            report["summary"]["assessed_cents"] - report["summary"]["paid_cents"],
        )
        self.assertEqual(
            self.client.get("/api/reports?date_from=2100-01-01").json()["summary"]["permit_count"],
            0,
        )
        self.assertEqual(self.client.get("/api/reports?municipality_id=2").status_code, 403)
        self.assertEqual(
            self.client.get("/api/reports?date_from=2026-12-01&date_to=2026-01-01").status_code, 422
        )
        self.assertEqual(self.client.get("/api/reports?date_from=bad").status_code, 422)
        exported = self.client.get("/api/reports/export")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("text/csv", exported.headers["content-type"])
        self.assertEqual(len(exported.text.splitlines()), 13)
        self.assertIn("DEMO-2026-0001", exported.text)
        self.assertNotIn("DEMO-CEDAR", exported.text)

    def test_csv_formula_injection_protection(self):
        from backend.db import connect

        with connect() as db:
            db.execute("UPDATE permits SET work_address='=HYPERLINK(\"malicious\")' WHERE id=1")
        data = self.client.get("/api/reports/export").text
        import csv
        import io

        rows = list(csv.DictReader(io.StringIO(data)))
        self.assertEqual(
            next(row["work_address"] for row in rows if row["number"] == "DEMO-2026-0001")[0], "'"
        )

    def test_database_constraints_and_audit_immutability(self):
        from backend.db import connect

        self.post(
            "/permits/1/payments", {"amount_cents": 100, "idempotency_key": "audit-test-payment"}
        )
        with connect() as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE permits SET applicant_id=4 WHERE id=1")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE audit_log SET action='tampered'")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM audit_log")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE permits SET fee_cents=0 WHERE id=1")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM payments")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE payments SET amount_cents=1")
        self.assertEqual(self.client.get("/api/permits/1").json()["paid_cents"], 100)

    def test_repeatable_migration_and_seed(self):
        from backend.db import connect, initialize

        initialize()
        initialize()
        with connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM permits").fetchone()[0], 13)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 6)
            self.assertGreaterEqual(
                db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], 1
            )
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")


if __name__ == "__main__":
    unittest.main()
