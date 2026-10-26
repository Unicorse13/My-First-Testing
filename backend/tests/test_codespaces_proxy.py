"""Regression coverage for the observed Codespaces proxy's mixed-hop headers.

The fixture models the exact screenshot: the HTTPS browser's Host and Origin are
rewritten to localhost HTTP, while X-Forwarded-Proto still describes outer HTTPS.
It uses Uvicorn's actual proxy middleware to reproduce the original rejection.
The fixed fixture leaves proxy-header interpretation disabled, as the demo
startup command does; the application's origin/CSRF policy remains unchanged.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from backend.main import _attempts, app

PUBLIC_ORIGIN = "https://proxy-regression-8000.app.github.dev"
INTERNAL_ORIGIN = "http://localhost:8000"
LOGIN = {"email": "admin@demo.permitsnj.test", "password": "DemoPermit2026!"}
PERMIT = {
    "applicant_id": 1,
    "contractor_id": 1,
    "type": "building",
    "description": "Synthetic proxy regression permit",
    "work_address": "42 Proxy Example Lane",
    "area_sqft": 100,
    "prior_approval": True,
}


class CodespacesProxy:
    """Test-only forwarding adapter, not an alternative application policy."""

    def __init__(self, interpret_proxy_headers=False, rewrite_origin=True):
        self.observed_scheme = None
        self.rewrite_origin = rewrite_origin
        target = self.capture_backend_request
        self.target = (
            ProxyHeadersMiddleware(target, trusted_hosts="127.0.0.1")
            if interpret_proxy_headers
            else target
        )

    async def capture_backend_request(self, scope, receive, send):
        if scope["type"] == "http":
            self.observed_scheme = scope["scheme"]
        await app(scope, receive, send)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.target(scope, receive, send)
            return
        forwarded = dict(scope)
        forwarded["scheme"] = "http"
        forwarded["client"] = ("127.0.0.1", 41234)
        forwarded["server"] = ("localhost", 8000)
        headers = dict(scope["headers"])
        headers[b"host"] = b"localhost:8000"
        headers.setdefault(b"x-forwarded-proto", b"https")
        headers[b"x-forwarded-for"] = b"203.0.113.20"
        # The fixture only rewrites a matching same-site browser Origin. A
        # foreign Origin must remain foreign so the real security check sees it.
        if self.rewrite_origin and headers.get(b"origin") == PUBLIC_ORIGIN.encode():
            headers[b"origin"] = INTERNAL_ORIGIN.encode()
        forwarded["headers"] = list(headers.items())
        await self.target(forwarded, receive, send)


class CodespacesProxyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="permitsnj-proxy-")
        self.env = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": str(Path(self.temp.name) / "proxy.sqlite3"),
                "DEMO_MODE": "true",
                "SESSION_SECURE": "true",
                "APP_ORIGIN": PUBLIC_ORIGIN,
            },
        )
        self.env.start()
        _attempts.clear()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def client(self, proxy):
        # Cookies are evaluated at the external HTTPS browser URL, even though
        # the fixture's private proxy-to-application hop is HTTP.
        return TestClient(proxy, base_url=PUBLIC_ORIGIN, headers={"Origin": PUBLIC_ORIGIN})

    def sign_in(self, client):
        result = client.post("/api/auth/login", json=LOGIN)
        self.assertEqual(result.status_code, 200, result.text)
        return result

    def test_uvicorn_forwarded_scheme_reproduces_observed_rejection(self):
        proxy = CodespacesProxy(interpret_proxy_headers=True)
        with self.client(proxy) as client:
            result = client.post("/api/auth/login", json=LOGIN)
            self.assertEqual(result.status_code, 403)
            self.assertEqual(proxy.observed_scheme, "https")
            self.assertIn(f"Expected browser address: {PUBLIC_ORIGIN}", result.text)
            self.assertIn(f"Received origin: {INTERNAL_ORIGIN}", result.text)
            self.assertIn("Server host: localhost:8000", result.text)

    def test_raw_hop_login_keeps_secure_cookie_and_scoped_records(self):
        proxy = CodespacesProxy()
        with self.client(proxy) as client:
            result = self.sign_in(client)
            self.assertEqual(proxy.observed_scheme, "http")
            cookie = result.headers["set-cookie"]
            self.assertIn("Secure", cookie)
            self.assertIn("HttpOnly", cookie)
            self.assertIn("SameSite=lax", cookie)
            self.assertTrue(client.cookies.get("permits_session"))
            self.assertEqual(client.get("/api/auth/me").json()["user"]["role"], "admin")
            permits = client.get("/api/permits").json()
            self.assertEqual(permits["total"], 12)
            self.assertTrue(all(row["municipality_id"] == 1 for row in permits["items"]))
            created = client.post(
                "/api/permits",
                json=PERMIT,
                headers={"X-CSRF-Token": result.json()["csrf_token"]},
            )
            self.assertEqual(created.status_code, 201, created.text)
            self.assertEqual(created.json()["fee_cents"], 17500)

    def test_csrf_is_required_after_proxy_login(self):
        with self.client(CodespacesProxy()) as client:
            result = self.sign_in(client)
            self.assertEqual(client.post("/api/permits", json=PERMIT).status_code, 403)
            self.assertEqual(
                client.post(
                    "/api/permits", json=PERMIT, headers={"X-CSRF-Token": "incorrect"}
                ).status_code,
                403,
            )
            accepted = client.post(
                "/api/permits",
                json=PERMIT,
                headers={"X-CSRF-Token": result.json()["csrf_token"]},
            )
            self.assertEqual(accepted.status_code, 201, accepted.text)

    def test_foreign_origin_rejected_despite_forwarded_headers(self):
        with self.client(CodespacesProxy()) as client:
            result = client.post(
                "/api/auth/login",
                json=LOGIN,
                headers={
                    "Origin": "https://foreign.example",
                    "X-Forwarded-Proto": "https",
                    "X-Forwarded-Host": PUBLIC_ORIGIN.removeprefix("https://"),
                },
            )
            self.assertEqual(result.status_code, 403)
            self.assertIn("Received origin: https://foreign.example", result.text)

    def test_unrewritten_exact_public_origin_still_works(self):
        with self.client(CodespacesProxy(rewrite_origin=False)) as client:
            self.sign_in(client)
            self.assertEqual(client.get("/api/auth/me").status_code, 200)

    def test_default_proxy_policy_remains_strict_outside_demo(self):
        proxy = CodespacesProxy(interpret_proxy_headers=True)
        with self.client(proxy) as client:
            # Startup seeds only the temporary demo DB. Changing the request-time
            # mode here checks that production errors remain strict and private.
            with patch.dict(os.environ, {"DEMO_MODE": "false"}):
                result = client.post("/api/auth/login", json=LOGIN)
            self.assertEqual(result.status_code, 403)
            self.assertEqual(result.json(), {"detail": "Cross-origin requests are not allowed."})
            self.assertNotIn(PUBLIC_ORIGIN, result.text)


if __name__ == "__main__":
    unittest.main()
