"""Versioned fee setup integration tests based on supplied S-01 and S-02 guides."""

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": self.directory.name + "/ref.sqlite3",
                "DEMO_MODE": "true",
                "SESSION_SECURE": "false",
            },
        )
        self.env.start()
        from backend.main import _attempts, app

        _attempts.clear()
        self.client = TestClient(app)
        self.client.__enter__()
        self.login()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.directory.cleanup()

    def login(self, role="admin"):
        self.client.headers.pop("X-CSRF-Token", None)
        response = self.client.post(
            "/api/auth/login",
            json={"email": role + "@demo.permitsnj.test", "password": "DemoPermit2026!"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.client.headers["X-CSRF-Token"] = response.json()["csrf_token"]

    def schedule(self, **overrides):
        body = {
            "subcode": "building",
            "effective_date": "2020-01-01",
            "ordinance_citation": "DEMO ordinance only",
            "items": [
                {"position": 1, "description": "Demo base", "basis": "fixed", "amount_cents": 1000},
                {
                    "position": 2,
                    "description": "Demo area",
                    "basis": "per_unit",
                    "amount_cents": 25,
                },
                {"position": 3, "description": "No fee item", "basis": "fixed", "amount_cents": 0},
            ],
        }
        return {**body, **overrides}

    def create(self, **overrides):
        response = self.client.post("/api/fee-schedules", json=self.schedule(**overrides))
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def activate(self, ident):
        return self.client.post(
            f"/api/fee-schedules/{ident}/activate", json={"confirmed_review": True}
        )

    def test_create_print_review_activate_immutable_and_audit(self):
        schedule = self.create(ordinance_citation="DEMO <script>alert(1)</script>")
        self.assertEqual(schedule["status"], "draft")
        self.assertEqual([x["position"] for x in schedule["items"]], [1, 2, 3])
        self.assertEqual(schedule["items"][2]["amount_cents"], 0)
        ident = schedule["id"]
        printed = self.client.get(f"/api/fee-schedules/{ident}/document")
        self.assertEqual(printed.status_code, 200)
        self.assertIn("DEMONSTRATION ONLY", printed.text)
        self.assertNotIn("<script>", printed.text)
        self.assertIn("&lt;script&gt;", printed.text)
        self.assertEqual(
            self.client.post(
                f"/api/fee-schedules/{ident}/activate", json={"confirmed_review": False}
            ).status_code,
            422,
        )
        self.assertEqual(self.activate(ident).status_code, 200)
        self.assertEqual(
            self.client.patch(
                f"/api/fee-schedules/{ident}", json={"min_fee_cents": 100}
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/fee-schedules/{ident}/items/1", json={"amount_cents": 1}
            ).status_code,
            409,
        )
        self.assertEqual(self.activate(ident).status_code, 409)
        from backend.db import connect

        with connect() as db:
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM audit_log WHERE entity='fee_schedule' AND action='activated'"
                ).fetchone()[0],
                1,
            )
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(
                    "UPDATE fee_schedule_items SET amount_cents=2 WHERE schedule_id=?", (ident,)
                )

    def test_copy_new_date_edit_and_append_without_reordering(self):
        original = self.create()
        ident = original["id"]
        self.assertEqual(self.activate(ident).status_code, 200)
        self.assertEqual(
            self.client.post(
                f"/api/fee-schedules/{ident}/copy", json={"effective_date": "2020-01-01"}
            ).status_code,
            422,
        )
        copied = self.client.post(
            f"/api/fee-schedules/{ident}/copy", json={"effective_date": "2021-01-01"}
        )
        self.assertEqual(copied.status_code, 201, copied.text)
        newer = copied.json()
        self.assertEqual(newer["status"], "draft")
        self.assertEqual(newer["copied_from_id"], ident)
        self.assertEqual(
            [x["description"] for x in newer["items"]],
            [x["description"] for x in original["items"]],
        )
        target = newer["id"]
        self.assertEqual(
            self.client.patch(
                f"/api/fee-schedules/{target}/items/1", json={"amount_cents": 2000}
            ).status_code,
            200,
        )
        append = {
            "position": 5,
            "description": "Ordinance extra",
            "basis": "fixed",
            "amount_cents": 50,
        }
        self.assertEqual(
            self.client.post(f"/api/fee-schedules/{target}/items", json=append).status_code, 422
        )
        append["position"] = 4
        self.assertEqual(
            self.client.post(f"/api/fee-schedules/{target}/items", json=append).status_code, 201
        )
        self.assertEqual(
            self.client.get(f"/api/fee-schedules/{ident}").json()["items"][0]["amount_cents"], 1000
        )

    def test_effective_date_resolution_and_minmax_exact_cents(self):
        original = self.create(min_fee_cents=2000, max_fee_cents=4000)
        ident = original["id"]
        from backend.db import connect
        from backend.reference import calculate_fee

        with connect() as db:
            self.assertIsNone(calculate_fee(db, 1, "building", 100, "2020-02-01"))
        self.activate(ident)
        copied = self.client.post(
            f"/api/fee-schedules/{ident}/copy", json={"effective_date": "2021-01-01"}
        ).json()
        self.client.patch(f"/api/fee-schedules/{copied['id']}/items/1", json={"amount_cents": 3000})
        self.activate(copied["id"])
        with connect() as db:
            self.assertIsNone(calculate_fee(db, 1, "building", 100, "2019-12-31"))
            self.assertIsNone(calculate_fee(db, 2, "building", 100, "2022-01-01"))
            self.assertEqual(calculate_fee(db, 1, "building", 0, "2020-06-01")["fee_cents"], 2000)
            self.assertEqual(calculate_fee(db, 1, "building", 50, "2020-06-01")["fee_cents"], 2250)
            self.assertEqual(calculate_fee(db, 1, "building", 999, "2020-06-01")["fee_cents"], 4000)
            self.assertEqual(calculate_fee(db, 1, "building", 0, "2021-01-01")["fee_cents"], 3000)

    def test_all_subcodes_and_building_use_group_variants(self):
        for subcode in ["building", "electrical", "elevator", "fire_protection", "plumbing"]:
            self.create(subcode=subcode)
        variant = self.create(use_group="R-demo")
        self.assertEqual(variant["use_group"], "R-demo")
        self.assertEqual(len(self.client.get("/api/fee-schedules").json()), 6)
        self.assertEqual(
            self.client.post(
                "/api/fee-schedules", json=self.schedule(subcode="plumbing", use_group="R")
            ).status_code,
            422,
        )

    def test_validation_duplicates_and_unsupported_official_bases(self):
        self.create()
        self.assertEqual(
            self.client.post("/api/fee-schedules", json=self.schedule()).status_code, 409
        )
        for updates in [
            {"min_fee_cents": 100, "max_fee_cents": 10},
            {"effective_date": "nonsense"},
            {"ordinance_citation": ""},
            {"items": []},
            {"subcode": "unknown"},
            {"items": [{"position": 2, "description": "Gap", "basis": "fixed", "amount_cents": 1}]},
            {
                "items": [
                    {
                        "position": 1,
                        "description": "No invented range algorithm",
                        "basis": "quantity_range",
                        "amount_cents": 1,
                    }
                ]
            },
        ]:
            self.assertEqual(
                self.client.post("/api/fee-schedules", json=self.schedule(**updates)).status_code,
                422,
            )

    def test_cross_municipality_roles_and_metadata(self):
        ident = self.create()["id"]
        self.login("clerk")
        self.assertEqual(self.activate(ident).status_code, 403)
        self.assertEqual(
            self.client.patch(
                f"/api/fee-schedules/{ident}", json={"min_fee_cents": 100}
            ).status_code,
            200,
        )
        self.login("reviewer")
        self.assertEqual(
            self.client.post("/api/fee-schedules", json=self.schedule()).status_code, 403
        )
        self.assertEqual(self.client.get("/api/reference-tables").status_code, 200)
        self.login("other")
        self.assertEqual(self.client.get("/api/fee-schedules").json(), [])
        self.assertEqual(self.client.get(f"/api/fee-schedules/{ident}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/fee-schedules/{ident}/document").status_code, 404)
        self.assertEqual(self.activate(ident).status_code, 404)
        self.login("applicant")
        for endpoint in [
            "/api/reference-tables",
            "/api/fee-schedules",
            f"/api/fee-schedules/{ident}/document",
        ]:
            self.assertEqual(self.client.get(endpoint).status_code, 403)
