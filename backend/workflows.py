"""Municipality-scoped permit workflows and a strictly mock payment provider."""

import csv
import hashlib
import html
import io
import json
import secrets
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from backend.db import connect
from backend.security import audit, current_user, get_permit, now, require_roles

router = APIRouter()
STAFF = ("admin", "clerk", "reviewer", "inspector")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PaymentInput(Input):
    amount_cents: StrictInt = Field(gt=0, le=100000000)
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    simulate_failure: bool = False


class ReviewInput(Input):
    result: Literal["approved", "changes_requested"]
    notes: str = Field(min_length=1, max_length=4000)


class InspectionInput(Input):
    inspector_id: int = Field(gt=0)
    scheduled_date: date


class InspectionResult(Input):
    result: Literal["passed", "failed"]
    notes: str = Field(min_length=1, max_length=4000)
    follow_up: str = Field(default="", max_length=4000)


class NoticeInput(Input):
    kind: Literal["notice", "order"]
    description: str = Field(min_length=1, max_length=4000)
    deadline: date


class NoticeUpdate(Input):
    status: Literal["resolved"]


def scope(user, alias="p"):
    condition = f"{alias}.municipality_id=?"
    params = [user["municipality_id"]]
    if user["role"] == "applicant":
        condition += f" AND {alias}.owner_id=?"
        params.append(user["id"])
    return condition, params


def public_payment(row):
    return {
        key: value
        for key, value in dict(row).items()
        if key not in ("request_hash", "idempotency_key")
    }


def workflow_list(table, user):
    condition, params = scope(user)
    with connect() as db:
        return [
            public_payment(row) if table == "payments" else dict(row)
            for row in db.execute(
                f"SELECT w.*,p.number AS permit_number,p.work_address FROM {table} w JOIN permits p ON p.id=w.permit_id WHERE {condition} ORDER BY w.id DESC LIMIT 1000",
                params,
            )
        ]


def record(db, table, ident, user):
    row = db.execute(f"SELECT * FROM {table} WHERE id=?", (ident,)).fetchone()
    if row is None:
        raise HTTPException(404, "Record not found")
    permit = get_permit(db, row["permit_id"], user)
    return row, permit


@router.get("/payments")
def payments(user=Depends(current_user)):
    return workflow_list("payments", user)


@router.get("/plan-reviews")
def reviews(user=Depends(current_user)):
    return workflow_list("plan_reviews", user)


@router.get("/inspections")
def inspections(user=Depends(current_user)):
    return workflow_list("inspections", user)


@router.get("/certificates")
def certificates(user=Depends(current_user)):
    return workflow_list("certificates", user)


@router.get("/notices")
def notices(user=Depends(current_user)):
    return workflow_list("notices", user)


@router.post("/permits/{permit_id}/payments")
def pay(permit_id: int, body: PaymentInput, response: Response, user=Depends(current_user)):
    require_roles(user, "admin", "clerk", "applicant")
    digest = hashlib.sha256(
        json.dumps(
            {
                "permit_id": permit_id,
                "amount_cents": body.amount_cents,
                "simulate_failure": body.simulate_failure,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        permit = get_permit(db, permit_id, user)
        previous = db.execute(
            "SELECT * FROM payments WHERE idempotency_key=?", (body.idempotency_key,)
        ).fetchone()
        if previous:
            if previous["permit_id"] != permit_id or previous["request_hash"] != digest:
                raise HTTPException(409, "Idempotency key was already used for a different request")
            response.status_code = 200
            return public_payment(previous)
        if body.simulate_failure:
            audit(
                db,
                user,
                "permit",
                permit_id,
                "payment_declined",
                {"provider": "mock", "amount_cents": body.amount_cents},
            )
            return JSONResponse(
                status_code=402,
                content={"detail": "Mock provider declined this payment. No money was collected."},
            )
        paid = db.execute(
            "SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE permit_id=?", (permit_id,)
        ).fetchone()[0]
        if body.amount_cents > permit["fee_cents"] - paid:
            raise HTTPException(409, "Payment exceeds the remaining balance")
        reference = "MOCK-" + secrets.token_hex(8).upper()
        cursor = db.execute(
            "INSERT INTO payments(permit_id,amount_cents,method,reference,idempotency_key,request_hash,created_at) VALUES (?,?,'mock',?,?,?,?)",
            (permit_id, body.amount_cents, reference, body.idempotency_key, digest, now()),
        )
        audit(
            db,
            user,
            "permit",
            permit_id,
            "payment_recorded",
            {"payment_id": cursor.lastrowid, "amount_cents": body.amount_cents, "provider": "mock"},
        )
        db.execute("UPDATE permits SET updated_at=? WHERE id=?", (now(), permit_id))
        response.status_code = 201
        return public_payment(
            db.execute("SELECT * FROM payments WHERE id=?", (cursor.lastrowid,)).fetchone()
        )


@router.post("/payments/{ident}/reconcile")
def reconcile(ident: int, user=Depends(current_user)):
    require_roles(user, "admin", "clerk")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row, permit = record(db, "payments", ident, user)
        if not row["reconciled"]:
            db.execute("UPDATE payments SET reconciled=1 WHERE id=?", (ident,))
            audit(db, user, "permit", permit["id"], "payment_reconciled", {"payment_id": ident})
        return public_payment(db.execute("SELECT * FROM payments WHERE id=?", (ident,)).fetchone())


@router.post("/permits/{permit_id}/plan-reviews", status_code=201)
def create_review(permit_id: int, body: ReviewInput, user=Depends(current_user)):
    require_roles(user, "admin", "reviewer")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        permit = get_permit(db, permit_id, user)
        if permit["status"] not in ("submitted", "under_review"):
            raise HTTPException(
                409, "Plan reviews require a submitted permit or a permit under review"
            )
        cursor = db.execute(
            "INSERT INTO plan_reviews(permit_id,reviewer_id,result,notes,created_at) VALUES (?,?,?,?,?)",
            (permit_id, user["id"], body.result, body.notes, now()),
        )
        audit(db, user, "permit", permit_id, "plan_review_recorded", body.model_dump())
        return dict(
            db.execute("SELECT * FROM plan_reviews WHERE id=?", (cursor.lastrowid,)).fetchone()
        )


@router.post("/permits/{permit_id}/inspections", status_code=201)
def schedule(permit_id: int, body: InspectionInput, user=Depends(current_user)):
    require_roles(user, "admin", "clerk")
    if body.scheduled_date < date.today():
        raise HTTPException(422, "Inspection date must be today or later")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        permit = get_permit(db, permit_id, user)
        if permit["status"] in ("draft", "closed"):
            raise HTTPException(409, "Inspections require an active submitted permit")
        inspector = db.execute(
            "SELECT id FROM users WHERE id=? AND municipality_id=? AND role='inspector'",
            (body.inspector_id, user["municipality_id"]),
        ).fetchone()
        if not inspector:
            raise HTTPException(422, "Choose an inspector in this municipality")
        existing = db.execute(
            "SELECT id FROM inspections WHERE permit_id=? AND inspector_id=? AND scheduled_date=? AND status='scheduled'",
            (permit_id, body.inspector_id, body.scheduled_date.isoformat()),
        ).fetchone()
        if existing:
            raise HTTPException(409, "This inspection is already scheduled")
        cursor = db.execute(
            "INSERT INTO inspections(permit_id,inspector_id,scheduled_date,created_at) VALUES (?,?,?,?)",
            (permit_id, body.inspector_id, body.scheduled_date.isoformat(), now()),
        )
        audit(db, user, "permit", permit_id, "inspection_scheduled", body.model_dump(mode="json"))
        return dict(
            db.execute("SELECT * FROM inspections WHERE id=?", (cursor.lastrowid,)).fetchone()
        )


@router.patch("/inspections/{ident}")
def inspection_result(ident: int, body: InspectionResult, user=Depends(current_user)):
    require_roles(user, "admin", "inspector")
    if body.result == "failed" and not body.follow_up:
        raise HTTPException(422, "A failed inspection requires a follow-up action")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row, permit = record(db, "inspections", ident, user)
        if user["role"] == "inspector" and row["inspector_id"] != user["id"]:
            raise HTTPException(403, "Only the assigned inspector can record this result")
        if row["status"] == "completed":
            raise HTTPException(
                409, "Inspection result is already recorded; schedule a follow-up inspection"
            )
        db.execute(
            "UPDATE inspections SET status='completed',result=?,notes=?,follow_up=? WHERE id=?",
            (body.result, body.notes, body.follow_up, ident),
        )
        audit(db, user, "permit", permit["id"], "inspection_completed", body.model_dump())
        return dict(db.execute("SELECT * FROM inspections WHERE id=?", (ident,)).fetchone())


@router.post("/permits/{permit_id}/certificates", status_code=201)
def issue_certificate(permit_id: int, user=Depends(current_user)):
    require_roles(user, "admin", "clerk")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        permit = get_permit(db, permit_id, user)
        paid = db.execute(
            "SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE permit_id=?", (permit_id,)
        ).fetchone()[0]
        inspection = db.execute(
            "SELECT result FROM inspections WHERE permit_id=? ORDER BY id DESC LIMIT 1",
            (permit_id,),
        ).fetchone()
        if (
            permit["status"] not in ("issued", "closed")
            or paid != permit["fee_cents"]
            or not inspection
            or inspection["result"] != "passed"
        ):
            raise HTTPException(
                409,
                "Certificate requires an issued or closed permit, full payment, and a latest passed inspection",
            )
        if db.execute(
            "SELECT 1 FROM certificates WHERE permit_id=? AND status='active'", (permit_id,)
        ).fetchone():
            raise HTTPException(409, "An active certificate already exists")
        number = "DEMO-CERT-" + secrets.token_hex(5).upper()
        cursor = db.execute(
            "INSERT INTO certificates(permit_id,number,created_at) VALUES (?,?,?)",
            (permit_id, number, now()),
        )
        audit(db, user, "permit", permit_id, "certificate_issued", {"number": number})
        return dict(
            db.execute("SELECT * FROM certificates WHERE id=?", (cursor.lastrowid,)).fetchone()
        )


@router.post("/certificates/{ident}/revoke")
def revoke(ident: int, user=Depends(current_user)):
    require_roles(user, "admin", "clerk")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row, permit = record(db, "certificates", ident, user)
        if row["status"] != "revoked":
            db.execute(
                "UPDATE certificates SET status='revoked',revoked_at=? WHERE id=?", (now(), ident)
            )
            audit(
                db, user, "permit", permit["id"], "certificate_revoked", {"certificate_id": ident}
            )
        return dict(db.execute("SELECT * FROM certificates WHERE id=?", (ident,)).fetchone())


@router.post("/permits/{permit_id}/notices", status_code=201)
def create_notice(permit_id: int, body: NoticeInput, user=Depends(current_user)):
    require_roles(user, "admin", "clerk")
    if body.deadline < date.today():
        raise HTTPException(422, "Deadline must be today or later")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        permit = get_permit(db, permit_id, user)
        cursor = db.execute(
            "INSERT INTO notices(permit_id,kind,description,deadline,created_at) VALUES (?,?,?,?,?)",
            (permit["id"], body.kind, body.description, body.deadline.isoformat(), now()),
        )
        audit(db, user, "permit", permit_id, "notice_issued", body.model_dump(mode="json"))
        return dict(db.execute("SELECT * FROM notices WHERE id=?", (cursor.lastrowid,)).fetchone())


@router.patch("/notices/{ident}")
def resolve_notice(ident: int, body: NoticeUpdate, user=Depends(current_user)):
    require_roles(user, "admin", "clerk")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row, permit = record(db, "notices", ident, user)
        if row["status"] != "resolved":
            db.execute("UPDATE notices SET status='resolved' WHERE id=?", (ident,))
            audit(db, user, "permit", permit["id"], "notice_resolved", {"notice_id": ident})
        return dict(db.execute("SELECT * FROM notices WHERE id=?", (ident,)).fetchone())


def document(title, fields):
    content = "".join(
        f"<dt>{html.escape(str(key))}</dt><dd>{html.escape(str(value))}</dd>"
        for key, value in fields
    )
    return HTMLResponse(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'
        + html.escape(title)
        + '</title><style>body{font:18px system-ui;max-width:800px;margin:60px auto;padding:20px;color:#183f36}h1{border-bottom:3px solid #183f36;padding-bottom:20px}dt{font-weight:bold;margin-top:20px}dd{margin:4px 0;white-space:pre-wrap}.demo{padding:15px;background:#fff0cf}@media print{body{margin:0}}</style><body><p class="demo">DEMONSTRATION ONLY · Not an official municipal document</p><h1>'
        + html.escape(title)
        + "</h1><dl>"
        + content
        + "</dl><p>Use your browser’s Print command to print or save as PDF.</p></body></html>",
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
        },
    )


@router.get("/certificates/{ident}/document")
def certificate_document(ident: int, user=Depends(current_user)):
    with connect() as db:
        row, permit = record(db, "certificates", ident, user)
        municipality = db.execute(
            "SELECT name FROM municipalities WHERE id=?", (permit["municipality_id"],)
        ).fetchone()[0]
        return document(
            "Demonstration certificate",
            [
                ("Certificate", row["number"]),
                ("Status", row["status"]),
                ("Municipality", municipality),
                ("Permit", permit["number"]),
                ("Work site", permit["work_address"]),
                ("Scope", permit["description"]),
                ("Issued", row["created_at"]),
                ("Revoked", row["revoked_at"] or "—"),
            ],
        )


@router.get("/notices/{ident}/document")
def notice_document(ident: int, user=Depends(current_user)):
    with connect() as db:
        row, permit = record(db, "notices", ident, user)
        return document(
            "Demonstration " + row["kind"],
            [
                ("Permit", permit["number"]),
                ("Work site", permit["work_address"]),
                ("Description", row["description"]),
                ("Deadline", row["deadline"]),
                ("Status", row["status"]),
                ("Created", row["created_at"]),
            ],
        )


def report_data(db, user, date_from, date_to, municipality_id):
    require_roles(user, *STAFF)
    if municipality_id is not None and municipality_id != user["municipality_id"]:
        raise HTTPException(403, "Reports are restricted to your municipality")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Start date must be on or before end date")
    condition, params = scope(user)
    if date_from:
        condition += " AND substr(p.created_at,1,10)>=?"
        params.append(date_from.isoformat())
    if date_to:
        condition += " AND substr(p.created_at,1,10)<=?"
        params.append(date_to.isoformat())
    rows = [
        dict(row)
        for row in db.execute(
            f"SELECT p.id,p.number,p.status,p.type,p.work_address,p.created_at,p.fee_cents,COALESCE((SELECT SUM(amount_cents) FROM payments WHERE permit_id=p.id),0) AS paid_cents FROM permits p WHERE {condition} ORDER BY p.created_at DESC,p.id DESC",
            params,
        )
    ]
    for row in rows:
        row["balance_cents"] = row["fee_cents"] - row["paid_cents"]
    return {
        "summary": {
            "permit_count": len(rows),
            "assessed_cents": sum(r["fee_cents"] for r in rows),
            "paid_cents": sum(r["paid_cents"] for r in rows),
            "balance_cents": sum(r["balance_cents"] for r in rows),
        },
        "items": rows,
    }


@router.get("/reports")
def reports(
    date_from: date | None = None,
    date_to: date | None = None,
    municipality_id: int | None = None,
    user=Depends(current_user),
):
    with connect() as db:
        return report_data(db, user, date_from, date_to, municipality_id)


@router.get("/reports/export")
def export(
    date_from: date | None = None,
    date_to: date | None = None,
    municipality_id: int | None = None,
    user=Depends(current_user),
):
    with connect() as db:
        data = report_data(db, user, date_from, date_to, municipality_id)
        audit(
            db,
            user,
            "report",
            0,
            "report_exported",
            {"date_from": str(date_from), "date_to": str(date_to), "count": len(data["items"])},
        )
    buffer = io.StringIO(newline="")
    fields = [
        "number",
        "status",
        "type",
        "work_address",
        "created_at",
        "fee_cents",
        "paid_cents",
        "balance_cents",
    ]
    writer = csv.writer(buffer)
    writer.writerow(fields)
    for row in data["items"]:
        # Prevent spreadsheet formula injection in user-controlled CSV strings.
        writer.writerow(
            [
                ("'" + str(row[key]))
                if isinstance(row[key], str)
                and row[key].lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
                else row[key]
                for key in fields
            ]
        )
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="permitsnj-demo-report.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/audit")
def audit_history(user=Depends(current_user)):
    require_roles(user, *STAFF)
    with connect() as db:
        return [
            dict(row)
            for row in db.execute(
                "SELECT a.*,u.name AS user_name FROM audit_log a JOIN users u ON u.id=a.user_id WHERE a.municipality_id=? ORDER BY a.id DESC LIMIT 100",
                (user["municipality_id"],),
            )
        ]
