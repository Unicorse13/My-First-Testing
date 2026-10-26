"""Real browser smoke using an isolated synthetic database and local ASGI server.

Run after `cd frontend && npm run build`: `python3 tests/browser_smoke.py`.
Requires Playwright and Chromium; CHROMIUM_PATH overrides /usr/bin/chromium.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise SystemExit("Build the frontend before running browser smoke.")
    with tempfile.TemporaryDirectory(prefix="permitsnj-browser-") as temporary:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        env = {
            **os.environ,
            "DEMO_MODE": "true",
            "SESSION_SECURE": "false",
            "DATABASE_PATH": str(Path(temporary) / "browser.sqlite3"),
            "ALLOWED_HOSTS": "127.0.0.1,localhost",
            "APP_ORIGIN": base,
        }
        with open(Path(temporary) / "server.log", "w+") as server_log:
            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "backend.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=ROOT,
                env=env,
                stdout=server_log,
                stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 15
                while True:
                    try:
                        with urlopen(base + "/api/health", timeout=1) as response:
                            assert json.load(response)["status"] == "ok"
                        break
                    except (OSError, ValueError):
                        if server.poll() is not None or time.monotonic() > deadline:
                            server_log.seek(0)
                            raise RuntimeError(
                                "API startup failed:\n" + server_log.read()
                            ) from None
                        time.sleep(0.1)
                run_browser(base)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


def run_browser(base):
    Path("/tmp/permitsnj-browser-failure.png").unlink(missing_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.getenv("CHROMIUM_PATH", "/usr/bin/chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000}, accept_downloads=True
        )
        page = context.new_page()
        failures = []
        page.on("pageerror", lambda error: failures.append(str(error)))
        page.set_default_timeout(10000)
        try:
            page.goto(base)
            page.get_by_role("button", name="Enter demo workspace").click()
            expect(page.get_by_role("heading", name="Welcome back, Admin.")).to_be_visible()
            expect(page.get_by_text("Mock payments", exact=False).first).to_be_visible()
            print("PASS desktop login and dashboard", flush=True)
            page.screenshot(
                path="/tmp/permitsnj-browser-desktop.png", full_page=True, animations="disabled"
            )

            page.get_by_role("button", name="New permit", exact=True).click()
            dialog = page.get_by_role("dialog").last
            dialog.get_by_label("Applicant", exact=False).select_option("1")
            dialog.get_by_label("Work-site address").fill("42 Browser Sample Lane")
            dialog.get_by_label("Description of proposed work").fill(
                "Browser synthetic deck application"
            )
            dialog.get_by_label("Work area (square feet)").fill("100")
            dialog.get_by_label("Prior approvals have been obtained").check()
            dialog.get_by_role("button", name="Create draft permit").click()
            expect(page.get_by_role("tab", name="Overview", exact=True)).to_be_visible()
            permit_dialog = page.get_by_role("dialog").first
            number = permit_dialog.get_by_role("heading", level=2).first.inner_text()
            assert re.fullmatch(r"DEMO-\d{4}-[A-F0-9]{8}", number), number
            expect(permit_dialog.get_by_text("$175.00", exact=True).first).to_be_visible()

            permit_dialog.get_by_role("button", name="Edit application").click()
            page.get_by_label("Description of proposed work").fill("Browser synthetic deck revised")
            expect(page.get_by_role("combobox", name=re.compile(r"^Applicant"))).to_have_value("1")
            page.get_by_role("button", name="Save permit", exact=True).click()
            expect(page.get_by_text("Browser synthetic deck revised", exact=True)).to_be_visible()
            print("PASS create/edit persistent permit and exact demo fee", flush=True)

            def transition(name):
                page.get_by_role("button", name=f"Move to {name}", exact=True).click()
                page.get_by_role("dialog").last.get_by_role(
                    "button", name="Confirm", exact=True
                ).click()
                expect(page.get_by_role("dialog")).to_have_count(1)

            transition("Submitted")
            expect(page.get_by_role("button", name="Move to Under Review")).to_be_visible()
            transition("Under Review")
            # The API must refuse approval before a plan review, and the UI must surface its error.
            page.get_by_role("button", name="Move to Approved", exact=True).click()
            page.get_by_role("dialog").last.get_by_role(
                "button", name="Confirm", exact=True
            ).click()
            expect(page.get_by_role("alert").last).to_contain_text("approved plan review")
            page.get_by_role("dialog").last.get_by_role("button", name="Cancel", exact=True).click()
            page.get_by_role("tab", name="Reviews", exact=True).click()
            page.get_by_role("button", name="Add review").click()
            page.get_by_label("Review decision").select_option("approved")
            page.get_by_label("Review notes").fill("Synthetic browser plan review approved")
            page.get_by_role("dialog").last.get_by_role("button", name="Save record").click()
            expect(
                page.get_by_text("Synthetic browser plan review approved", exact=True)
            ).to_be_visible()
            page.get_by_role("tab", name="Overview", exact=True).click()
            transition("Approved")
            print("PASS submission, review guard, review and approval", flush=True)

            page.get_by_role("tab", name="Payments", exact=True).click()
            page.get_by_role("button", name="Record mock payment").click()
            page.get_by_label("Mock payment amount ($)").fill("50")
            page.get_by_role("button", name="Submit mock payment").click()
            expect(page.get_by_text("Mock provider · Remaining balance $125.00")).to_be_visible()
            page.get_by_role("button", name="Record mock payment").click()
            page.get_by_label("Mock payment amount ($)").fill("25")
            page.get_by_label("Simulate a provider decline").check()
            page.get_by_role("button", name="Submit mock payment").click()
            expect(page.get_by_role("alert").last).to_contain_text("Mock provider declined")
            page.get_by_label("Simulate a provider decline").uncheck()
            page.get_by_label("Mock payment amount ($)").fill("125")
            page.get_by_role("button", name="Submit mock payment").click()
            expect(page.get_by_text("Mock provider · Remaining balance $0.00")).to_be_visible()
            page.get_by_role("button", name="Reconcile", exact=True).first.click()
            page.get_by_role("dialog").last.get_by_role(
                "button", name="Confirm", exact=True
            ).click()
            expect(page.get_by_role("dialog")).to_have_count(1)
            print("PASS partial/declined/full mock payments and reconciliation", flush=True)

            page.get_by_role("tab", name="Inspections", exact=True).click()
            page.get_by_role("button", name="Schedule inspection").click()
            page.get_by_label("Assigned inspector").select_option("4")
            tomorrow = (date.today() + timedelta(days=1)).isoformat()
            page.get_by_label("Inspection date").fill(tomorrow)
            page.get_by_role("dialog").last.get_by_role("button", name="Save record").click()
            page.get_by_role("button", name="Record result").click()
            page.get_by_role("combobox", name=re.compile(r"^Inspection result")).select_option(
                "passed"
            )
            page.get_by_label("Inspector notes").fill("Synthetic browser inspection passed")
            page.get_by_role("dialog").last.get_by_role("button", name="Save changes").click()
            expect(
                page.get_by_text("Synthetic browser inspection passed", exact=True)
            ).to_be_visible()
            page.get_by_role("tab", name="Overview", exact=True).click()
            transition("Issued")
            page.get_by_role("tab", name="Documents", exact=True).click()
            page.get_by_role("button", name="Generate certificate").click()
            page.get_by_role("dialog").last.get_by_role(
                "button", name="Confirm", exact=True
            ).click()
            expect(page.get_by_role("button", name="Revoke", exact=True)).to_be_visible()
            with page.expect_popup() as popup:
                page.get_by_role("link", name="View / print", exact=True).first.click()
            document = popup.value
            expect(
                document.get_by_role("heading", name="Demonstration certificate")
            ).to_be_visible()
            expect(document.get_by_text(number, exact=True)).to_be_visible()
            document.close()
            print(
                "PASS inspection assignment/result, issuance and authenticated certificate",
                flush=True,
            )

            page.get_by_role("button", name="Create notice").click()
            page.get_by_label("Document type").select_option("notice")
            page.get_by_label("Compliance deadline").fill(tomorrow)
            page.get_by_label("Description and required action").fill(
                "Synthetic browser notice for sample action"
            )
            page.get_by_role("dialog").last.get_by_role("button", name="Save record").click()
            expect(
                page.get_by_text("Synthetic browser notice for sample action", exact=True)
            ).to_be_visible()
            with page.expect_popup() as popup:
                page.get_by_role("link", name="View / print", exact=True).last.click()
            document = popup.value
            expect(document.get_by_role("heading", name="Demonstration notice")).to_be_visible()
            document.close()
            page.get_by_role("button", name="Resolve", exact=True).click()
            page.get_by_role("dialog").last.get_by_role(
                "button", name="Confirm", exact=True
            ).click()
            expect(page.get_by_text("Resolved", exact=True)).to_be_visible()
            # Escape on a nested action must close only that action.
            page.get_by_role("button", name="Revoke", exact=True).click()
            page.keyboard.press("Escape")
            expect(page.get_by_role("dialog")).to_have_count(1)
            page.get_by_role("dialog").first.get_by_role(
                "button", name="Close dialog", exact=True
            ).first.click()
            print("PASS notice lifecycle, printable access and nested-dialog recovery", flush=True)

            navigation = page.get_by_role("navigation", name="Main navigation")
            navigation.get_by_role("button", name=re.compile(r"^Permits(?: ↗)?$")).click()
            page.get_by_label("Search permits").fill("bRoWsEr SaMpLe")
            expect(page.get_by_role("button", name=number, exact=True)).to_be_visible()
            expect(page.locator("tbody tr")).to_have_count(1)
            page.get_by_label("Filter by status").select_option("issued")
            expect(page.get_by_role("button", name=number, exact=True)).to_be_visible()
            page.get_by_label("Search permits").fill("")
            page.get_by_label("Filter by status").select_option("")
            expect(page.get_by_role("button", name="Next page", exact=True)).to_be_enabled()
            page.get_by_role("button", name="Next page", exact=True).click()
            expect(page.get_by_text("Page 2", exact=True)).to_be_visible()
            print("PASS case-insensitive partial search, filters and pagination", flush=True)

            navigation.get_by_role("button", name="Reports", exact=True).click()
            expect(page.get_by_role("heading", name="Permit detail report")).to_be_visible()
            with page.expect_download() as download_info:
                page.get_by_role("link", name="Export CSV").click()
            download = download_info.value
            report = Path(download.path()).read_text()
            assert number in report and "paid_cents" in report, report
            print("PASS report table and actual CSV download", flush=True)

            navigation.get_by_role("button", name="Fees & Setup", exact=True).click()
            expect(page.get_by_role("heading", name="Reference table inventory")).to_be_visible()
            expect(page.get_by_role("heading", name="Additional Fees", exact=True)).to_be_visible()
            page.get_by_role("button", name="New draft schedule").click()
            page.get_by_role("dialog").last.get_by_label("Subcode", exact=False).select_option(
                "elevator"
            )
            page.get_by_label("Ordinance / reference citation").fill("DEMO browser reference only")
            page.get_by_label("Description / unit").fill("Synthetic fixed elevator application")
            page.get_by_label("Amount ($)", exact=False).fill("25.00")
            page.get_by_role("button", name="Create draft schedule").click()
            page.get_by_role("button", name="Details", exact=True).click()
            with page.expect_popup() as popup:
                page.get_by_role("link", name="View / print", exact=True).click()
            document = popup.value
            expect(document.get_by_text("DEMO browser reference only", exact=False)).to_be_visible()
            document.close()
            page.get_by_role("button", name="Review & activate").click()
            page.get_by_label(
                "I reviewed this demonstration schedule and confirm activation."
            ).check()
            page.get_by_role("button", name="Activate reviewed schedule").click()
            expect(page.locator("tbody").first.get_by_text("Active", exact=True)).to_be_visible()
            print(
                "PASS reference catalog and create/print/review/activate fee schedule", flush=True
            )

            page.get_by_role("button", name="Sign out", exact=True).click()
            page.get_by_label("Explore as").select_option("applicant")
            page.get_by_role("button", name="Enter demo workspace").click()
            expect(page.get_by_role("heading", name="Welcome back, Applicant.")).to_be_visible()
            page.get_by_role("navigation", name="Main navigation").get_by_role(
                "button", name=re.compile(r"^Permits(?: ↗)?$")
            ).click()
            page.get_by_label("Search permits").fill(number)
            expect(page.get_by_role("button", name=number, exact=True)).to_be_visible()
            expect(
                page.get_by_role("navigation", name="Main navigation").get_by_role(
                    "button", name="Reports", exact=True
                )
            ).to_have_count(0)
            print("PASS applicant ownership and role-specific navigation", flush=True)

            page.set_viewport_size({"width": 375, "height": 812})
            page.get_by_role("button", name="Open navigation").click()
            page.get_by_role("navigation", name="Main navigation").get_by_role(
                "button", name="Dashboard", exact=True
            ).click()
            expect(page.get_by_role("heading", name="Welcome back, Applicant.")).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                "Mobile body overflows viewport"
            )
            page.screenshot(
                path="/tmp/permitsnj-browser-mobile.png", full_page=True, animations="disabled"
            )
            assert not failures, failures
            print("PASS 375px mobile navigation/layout and no browser runtime errors", flush=True)
        except Exception:
            page.screenshot(
                path="/tmp/permitsnj-browser-failure.png", full_page=True, animations="disabled"
            )
            print("Browser failure screenshot: /tmp/permitsnj-browser-failure.png", flush=True)
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    main()
