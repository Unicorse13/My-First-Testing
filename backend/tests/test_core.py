"""Core API integration tests against isolated real SQLite databases."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.db import connect
from backend.main import _attempts, app


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": str(Path(self.temp.name) / "test.sqlite3"),
                "DEMO_MODE": "true",
                "SESSION_SECURE": "false",
            },
        )
        self.env.start()
        _attempts.clear()
        self.client = TestClient(app)
        self.client.__enter__()
        self.login("admin")

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    def login(self, role):
        email = ("other" if role == "other" else role) + "@demo.permitsnj.test"
        result = self.client.post(
            "/api/auth/login", json={"email": email, "password": "DemoPermit2026!"}
        )
        self.assertEqual(result.status_code, 200, result.text)
        self.csrf = result.json()["csrf_token"]
        return result

    def post(self, url, data):
        return self.client.post(url, json=data, headers={"X-CSRF-Token": self.csrf})

    def create(self, **overrides):
        result = self.post(
            "/api/permits",
            {
                "applicant_id": 1,
                "contractor_id": 1,
                "type": "building",
                "description": "Synthetic test deck",
                "work_address": "42 Sample Street",
                "area_sqft": 100,
                "prior_approval": True,
                **overrides,
            },
        )
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def test_auth_cookie_csrf_logout_and_expiry(self):
        login = self.login("clerk")
        cookie = login.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=lax", cookie)
        self.assertEqual(self.client.get("/api/auth/me").json()["user"]["role"], "clerk")
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 403)
        self.assertEqual(self.post("/api/auth/logout", {}).status_code, 200)
        self.assertEqual(self.client.get("/api/permits").status_code, 401)

    def test_bad_login_and_validation_does_not_echo_password(self):
        result = self.client.post(
            "/api/auth/login", json={"email": "unknown@example.test", "password": "bogus"}
        )
        self.assertEqual(result.status_code, 401)
        result = self.client.post(
            "/api/auth/login",
            json={"email": "x", "password": "DoNotEchoThis", "extra": "forbidden"},
        )
        self.assertEqual(result.status_code, 422)
        self.assertNotIn("DoNotEchoThis", result.text)

    def test_origin_csrf_and_request_size(self):
        self.assertEqual(
            self.client.post(
                "/api/auth/login",
                json={"email": "admin@demo.permitsnj.test", "password": "DemoPermit2026!"},
                headers={"Origin": "https://evil.example"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post("/api/permits", json={}, headers={"X-CSRF-Token": "bad"}).status_code,
            403,
        )
        self.assertEqual(self.client.post("/api/auth/login", content=b"x" * 65537).status_code, 413)
        self.assertEqual(
            self.client.get("/api/health").headers["x-content-type-options"], "nosniff"
        )

    def test_login_rate_limit(self):
        for _ in range(15):
            self.client.post(
                "/api/auth/login", json={"email": "none@example.test", "password": "bogus"}
            )
        result = self.client.post(
            "/api/auth/login", json={"email": "none@example.test", "password": "bogus"}
        )
        self.assertEqual(result.status_code, 429)

    def test_create_persistent_fee_and_validation(self):
        permit = self.create()
        self.assertEqual(permit["fee_cents"], 17500)
        self.assertEqual(permit["balance_cents"], 17500)
        self.assertEqual(
            self.client.get(f"/api/permits/{permit['id']}").json()["description"],
            "Synthetic test deck",
        )
        with connect() as db:
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM permits WHERE id=?", (permit["id"],)).fetchone()[
                    0
                ],
                1,
            )
        bad = self.post(
            "/api/permits",
            {
                "applicant_id": 1,
                "type": "unknown",
                "description": "valid description",
                "work_address": "123 Some Street",
            },
        )
        self.assertEqual(bad.status_code, 422)

    def test_case_insensitive_partial_search_sort_filter_pagination(self):
        self.create(description="Distinctive xYzNeedle application")
        found = self.client.get("/api/permits", params={"q": "XYZneedle"}).json()
        self.assertEqual(found["total"], 1)
        self.assertEqual(
            self.client.get("/api/permits", params={"page_size": 2}).json()["items"].__len__(), 2
        )
        result = self.client.get(
            "/api/permits", params={"type": "electrical", "sort": "number", "direction": "asc"}
        ).json()
        self.assertTrue(all(x["type"] == "electrical" for x in result["items"]))
        self.assertEqual(
            self.client.get("/api/permits", params={"sort": "1;DROP TABLE users"}).status_code, 422
        )
        self.assertEqual(self.client.get("/api/permits", params={"q": "%"}).json()["total"], 0)

    def test_unicode_partial_search(self):
        self.create(description="Synthetic Café Straße permit")
        for query in ("CAFÉ", "STRASSE", "café str"):
            result = self.client.get("/api/permits", params={"q": query})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["total"], 1)

    def test_edit_recalculate_and_audit(self):
        permit = self.create()
        result = self.client.patch(
            f"/api/permits/{permit['id']}",
            json={"area_sqft": 200},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["fee_cents"], 20000)
        self.assertTrue(any(x["action"] == "updated" for x in result.json()["audit"]))
        null = self.client.patch(
            f"/api/permits/{permit['id']}",
            json={"area_sqft": None},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(null.status_code, 422)

    def test_exemption_reason_and_reassessment(self):
        permit = self.create()
        url = f"/api/permits/{permit['id']}/exemption"
        self.assertEqual(self.post(url, {"exempt": True, "reason": ""}).status_code, 422)
        self.assertEqual(
            self.post(url, {"exempt": True, "reason": "Synthetic public project"}).json()[
                "fee_cents"
            ],
            0,
        )
        self.assertEqual(
            self.post(url, {"exempt": False, "reason": "Demo exemption ended"}).json()["fee_cents"],
            17500,
        )

    def test_paid_fee_reduction_is_rejected(self):
        permit = self.create()
        payment = self.post(
            f"/api/permits/{permit['id']}/payments",
            {"amount_cents": 17000, "idempotency_key": "core-balance-1"},
        )
        self.assertEqual(payment.status_code, 201, payment.text)
        reduced = self.client.patch(
            f"/api/permits/{permit['id']}",
            json={"area_sqft": 0},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(reduced.status_code, 409)
        self.assertEqual(
            self.post(
                f"/api/permits/{permit['id']}/exemption",
                {"exempt": True, "reason": "Synthetic exception"},
            ).status_code,
            409,
        )

    def test_lifecycle_prerequisites(self):
        permit = self.create(prior_approval=False)
        url = f"/api/permits/{permit['id']}"
        self.assertEqual(self.post(url + "/status", {"status": "submitted"}).status_code, 409)
        self.client.patch(url, json={"prior_approval": True}, headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(self.post(url + "/status", {"status": "submitted"}).status_code, 200)
        self.assertEqual(self.post(url + "/status", {"status": "issued"}).status_code, 409)
        self.assertEqual(self.post(url + "/status", {"status": "under_review"}).status_code, 200)
        self.assertEqual(self.post(url + "/status", {"status": "approved"}).status_code, 409)
        self.assertEqual(
            self.post(
                url + "/plan-reviews", {"result": "approved", "notes": "Synthetic complete plans"}
            ).status_code,
            201,
        )
        self.assertEqual(self.post(url + "/status", {"status": "approved"}).status_code, 200)
        self.assertEqual(self.post(url + "/status", {"status": "issued"}).status_code, 409)
        self.post(url + "/payments", {"amount_cents": 17500, "idempotency_key": "core-full-1"})
        self.assertEqual(self.post(url + "/status", {"status": "issued"}).status_code, 200)
        self.assertEqual(self.post(url + "/status", {"status": "closed"}).status_code, 409)

    def test_role_and_applicant_ownership(self):
        admin_permit = self.create(applicant_id=2)
        self.login("applicant")
        self.assertEqual(self.client.get(f"/api/permits/{admin_permit['id']}").status_code, 404)
        permit = self.create()
        self.assertEqual(
            self.post(
                f"/api/permits/{permit['id']}/exemption",
                {"exempt": True, "reason": "Unauthorized example"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                "/api/applicants", {"name": "Someone", "email": "x@example.test"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(f"/api/permits/{permit['id']}/status", {"status": "submitted"}).status_code,
            200,
        )
        result = self.client.patch(
            f"/api/permits/{permit['id']}",
            json={"description": "Not allowed after submitting"},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(result.status_code, 409)
        self.assertEqual(
            self.post(
                "/api/permits",
                {
                    "applicant_id": 2,
                    "type": "electrical",
                    "description": "Another person record",
                    "work_address": "123 Example Street",
                },
            ).status_code,
            403,
        )

    def test_cross_municipality_directory_and_permits(self):
        permit = self.create()
        self.assertEqual(
            self.post(
                "/api/permits",
                {
                    "applicant_id": 4,
                    "type": "building",
                    "description": "Invalid tenant test",
                    "work_address": "42 Test Street",
                },
            ).status_code,
            422,
        )
        self.login("other")
        self.assertEqual(self.client.get(f"/api/permits/{permit['id']}").status_code, 404)
        self.assertEqual(len(self.client.get("/api/permits").json()["items"]), 1)
        self.assertTrue(
            all(x["municipality_id"] == 2 for x in self.client.get("/api/applicants").json())
        )

    def test_transfer_draft_and_isolation(self):
        permit = self.create()
        transfer = self.post(
            f"/api/permits/{permit['id']}/transfer",
            {"municipality_id": 2, "applicant_id": 4, "contractor_id": 3},
        )
        self.assertEqual(transfer.status_code, 200, transfer.text)
        self.assertEqual(self.client.get(f"/api/permits/{permit['id']}").status_code, 404)
        self.login("other")
        result = self.client.get(f"/api/permits/{permit['id']}").json()
        self.assertEqual(result["municipality_id"], 2)
        self.assertEqual(result["prior_approval"], 0)

    def test_directories_and_configuration(self):
        applicant = self.post(
            "/api/applicants", {"name": "Casey Demo", "email": "CASEY@example.test"}
        )
        self.assertEqual(applicant.status_code, 201, applicant.text)
        self.assertEqual(applicant.json()["email"], "casey@example.test")
        contractor = self.post(
            "/api/contractors", {"name": "Synthetic Works", "license_number": "DEMO-T1"}
        )
        self.assertEqual(contractor.status_code, 201)
        self.assertEqual(
            self.post(
                "/api/contractors", {"name": "Synthetic Works", "license_number": "DEMO-T1"}
            ).status_code,
            409,
        )
        config = self.client.get("/api/config").json()
        self.assertNotIn("password_hash", str(config))
        self.assertEqual(len(config["statuses"]), 6)
        self.login("inspector")
        self.assertEqual(
            self.post(
                "/api/statuses", {"code": "custom", "label": "Custom", "next_statuses": []}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                "/api/permits",
                {
                    "applicant_id": 1,
                    "type": "plumbing",
                    "description": "Role denial test",
                    "work_address": "42 Test Street",
                },
            ).status_code,
            403,
        )

    def test_dashboard_and_unknown_api(self):
        board = self.client.get("/api/dashboard").json()
        self.assertEqual(board["permit_count"], 12)
        self.assertGreater(board["outstanding_cents"], 0)
        self.assertEqual(self.client.get("/api/not-an-endpoint").status_code, 404)

    def test_staff_creation_assigns_provisioned_applicant(self):
        permit = self.create()
        self.login("applicant")
        result = self.client.get(f"/api/permits/{permit['id']}")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["owner_id"], 5)

    def test_review_staleness_ignores_payment_but_not_application_edits(self):
        permit = self.create()
        base = f"/api/permits/{permit['id']}"
        self.post(base + "/status", {"status": "submitted"})
        self.post(base + "/plan-reviews", {"result": "approved", "notes": "First synthetic review"})
        self.post(
            base + "/payments", {"amount_cents": 100, "idempotency_key": "review-payment-key"}
        )
        self.post(base + "/status", {"status": "under_review"})
        self.assertEqual(self.post(base + "/status", {"status": "approved"}).status_code, 200)
        other = self.create()
        base = f"/api/permits/{other['id']}"
        self.post(base + "/status", {"status": "submitted"})
        self.post(base + "/status", {"status": "under_review"})
        self.post(base + "/plan-reviews", {"result": "approved", "notes": "Stale synthetic review"})
        self.client.patch(
            base,
            json={"description": "Changed scope after plan approval"},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(self.post(base + "/status", {"status": "approved"}).status_code, 409)

    def test_status_configuration_is_municipality_scoped(self):
        self.assertEqual(
            self.post(
                "/api/statuses",
                {"code": "on_hold", "label": "Local hold", "next_statuses": ["submitted"]},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.post(
                "/api/statuses",
                {
                    "code": "draft",
                    "label": "Local draft",
                    "next_statuses": ["submitted", "on_hold"],
                },
            ).status_code,
            200,
        )
        mine = self.client.get("/api/statuses").json()
        self.assertTrue(any(x["code"] == "on_hold" for x in mine))
        self.login("other")
        theirs = self.client.get("/api/statuses").json()
        self.assertFalse(any(x["code"] == "on_hold" for x in theirs))
        self.assertEqual(next(x["label"] for x in theirs if x["code"] == "draft"), "Draft")

    def test_active_schedule_assessment_and_fee_snapshot(self):
        result = self.post(
            "/api/fee-schedules",
            {
                "subcode": "building",
                "effective_date": "2020-01-01",
                "ordinance_citation": "DEMO test only",
                "items": [
                    {
                        "position": 1,
                        "description": "Demo base",
                        "basis": "fixed",
                        "amount_cents": 12345,
                    }
                ],
            },
        )
        self.assertEqual(result.status_code, 201, result.text)
        schedule = result.json()["id"]
        self.assertEqual(
            self.post(
                f"/api/fee-schedules/{schedule}/activate", {"confirmed_review": True}
            ).status_code,
            200,
        )
        permit = self.create()
        self.assertEqual(permit["fee_cents"], 12345)
        self.assertEqual(permit["assessed_schedule_id"], schedule)
        second = self.post(
            "/api/fee-schedules",
            {
                "subcode": "building",
                "effective_date": "2021-01-01",
                "ordinance_citation": "DEMO amendment",
                "items": [
                    {
                        "position": 1,
                        "description": "New demo base",
                        "basis": "fixed",
                        "amount_cents": 25000,
                    }
                ],
            },
        ).json()["id"]
        self.post(f"/api/fee-schedules/{second}/activate", {"confirmed_review": True})
        edited = self.client.patch(
            f"/api/permits/{permit['id']}",
            json={"description": "Unrelated wording change"},
            headers={"X-CSRF-Token": self.csrf},
        ).json()
        self.assertEqual(edited["fee_cents"], 12345)
        self.assertEqual(edited["assessed_schedule_id"], schedule)
        edited = self.client.patch(
            f"/api/permits/{permit['id']}",
            json={"area_sqft": 150},
            headers={"X-CSRF-Token": self.csrf},
        ).json()
        self.assertEqual(edited["fee_cents"], 25000)
        self.assertEqual(edited["assessed_schedule_id"], second)

    def test_missing_unsupported_demo_fee_schedule_and_group(self):
        for fields in [{"type": "elevator"}, {"type": "building", "use_group": "UNCONFIGURED"}]:
            result = self.post(
                "/api/permits",
                {
                    "applicant_id": 1,
                    "description": "Test no supplied rate",
                    "work_address": "42 Synthetic Lane",
                    **fields,
                },
            )
            self.assertEqual(result.status_code, 409, result.text)

    def test_demo_database_cannot_be_misrepresented_as_non_demo(self):
        with patch.dict(os.environ, {"DEMO_MODE": "false"}):
            with self.assertRaisesRegex(RuntimeError, "published demo accounts"):
                with TestClient(app):
                    pass

    def test_expired_session_and_secure_cookie(self):
        with connect() as db:
            db.execute("UPDATE sessions SET expires_at='2000-01-01T00:00:00+00:00'")
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        with patch.dict(os.environ, {"SESSION_SECURE": "true"}):
            result = self.login("admin")
            self.assertIn("Secure", result.headers["set-cookie"])
            self.assertIn("max-age", result.headers["strict-transport-security"])


if __name__ == "__main__":
    unittest.main()
