"""Permit lifecycle, directory and configuration API."""

import json
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .db import connect
from .security import audit, current_user, demo_mode, get_permit, now, require_roles

router = APIRouter()
STAFF = ("admin", "clerk", "reviewer", "inspector")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PermitInput(Input):
    applicant_id: int = Field(gt=0)
    contractor_id: int | None = Field(default=None, gt=0)
    type: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=5, max_length=2000)
    work_address: str = Field(min_length=5, max_length=300)
    area_sqft: int = Field(default=0, ge=0, le=1000000)
    prior_approval: bool = False
    use_group: str = Field(default="", max_length=40)


class PermitPatch(Input):
    applicant_id: int | None = Field(default=None, gt=0)
    contractor_id: int | None = Field(default=None, gt=0)
    type: str | None = Field(default=None, min_length=1, max_length=40)
    description: str | None = Field(default=None, min_length=5, max_length=2000)
    work_address: str | None = Field(default=None, min_length=5, max_length=300)
    area_sqft: int | None = Field(default=None, ge=0, le=1000000)
    prior_approval: bool | None = None
    use_group: str | None = Field(default=None, max_length=40)


class StatusInput(Input):
    status: str = Field(min_length=1, max_length=40)


class ExemptionInput(Input):
    exempt: bool
    reason: str = Field(default="", max_length=1000)


class TransferInput(Input):
    municipality_id: int = Field(gt=0)
    applicant_id: int = Field(gt=0)
    contractor_id: int | None = Field(default=None, gt=0)


class ApplicantInput(Input):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    phone: str = Field(default="", max_length=40)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        if (
            "@" not in value
            or "." not in value.rsplit("@", 1)[-1]
            or any(c.isspace() for c in value)
        ):
            raise ValueError("Enter a valid email address.")
        return value.lower()


class ContractorInput(Input):
    name: str = Field(min_length=2, max_length=120)
    license_number: str = Field(min_length=2, max_length=80)
    email: str = Field(default="", max_length=254)


class StatusConfig(Input):
    code: str = Field(pattern=r"^[a-z][a-z_]{1,39}$")
    label: str = Field(min_length=2, max_length=80)
    next_statuses: list[str] = Field(max_length=20)


def scope(user, alias="p"):
    clause = f"{alias}.municipality_id=?"
    args = [user["municipality_id"]]
    if user["role"] == "applicant":
        clause += f" AND {alias}.owner_id=?"
        args.append(user["id"])
    return clause, args


SELECT_PERMIT = """SELECT p.*, a.name applicant_name, c.name contractor_name, m.name municipality_name,
 COALESCE((SELECT SUM(amount_cents) FROM payments pay WHERE pay.permit_id=p.id),0) paid_cents,
 p.fee_cents-COALESCE((SELECT SUM(amount_cents) FROM payments pay WHERE pay.permit_id=p.id),0) balance_cents
 FROM permits p JOIN applicants a ON a.id=p.applicant_id
 LEFT JOIN contractors c ON c.id=p.contractor_id JOIN municipalities m ON m.id=p.municipality_id"""


def detail(db, permit_id, user):
    get_permit(db, permit_id, user)
    result = dict(db.execute(SELECT_PERMIT + " WHERE p.id=?", (permit_id,)).fetchone())
    for table in ("plan_reviews", "inspections", "payments", "certificates", "notices"):
        result[table] = [
            dict(x)
            for x in db.execute(
                f"SELECT * FROM {table} WHERE permit_id=? ORDER BY id DESC", (permit_id,)
            )
        ]
    # Financial request hashes and idempotency keys are implementation metadata, not document content.
    for payment in result["payments"]:
        payment.pop("request_hash", None)
        payment.pop("idempotency_key", None)
    result["audit"] = [
        dict(x)
        for x in db.execute(
            "SELECT * FROM audit_log WHERE entity='permit' AND entity_id=? AND municipality_id=? ORDER BY id DESC",
            (permit_id, user["municipality_id"]),
        )
    ]
    return result


def validate_parties(db, municipality_id, applicant_id, contractor_id, user=None):
    applicant = db.execute(
        "SELECT * FROM applicants WHERE id=? AND municipality_id=?", (applicant_id, municipality_id)
    ).fetchone()
    if applicant is None:
        raise HTTPException(422, "Choose an applicant in the selected municipality.")
    if user and user["role"] == "applicant" and applicant["email"].lower() != user["email"].lower():
        raise HTTPException(403, "You may apply only for yourself.")
    if (
        contractor_id is not None
        and not db.execute(
            "SELECT id FROM contractors WHERE id=? AND municipality_id=?",
            (contractor_id, municipality_id),
        ).fetchone()
    ):
        raise HTTPException(422, "Choose a contractor in the selected municipality.")


def fee(db, permit_type, area, municipality_id, use_group=""):
    from .reference import calculate_fee

    if permit_type != "building" and use_group:
        raise HTTPException(422, "Use group applies to building schedules only.")
    assessed = calculate_fee(db, municipality_id, permit_type, area, now()[:10], use_group)
    if assessed is not None:
        return assessed
    rule = db.execute("SELECT * FROM permit_types WHERE code=?", (permit_type,)).fetchone()
    if rule is None:
        raise HTTPException(422, "Unknown permit type.")
    if not demo_mode() or permit_type not in ("building", "electrical", "plumbing") or use_group:
        raise HTTPException(
            409,
            "Configure and activate a matching effective fee schedule first. No official rates are bundled.",
        )
    return {
        "fee_cents": rule["base_fee_cents"] + rule["area_rate_cents"] * area,
        "schedule_id": None,
    }


def status_definitions(db, municipality_id):
    return [
        {**dict(row), "next_statuses": json.loads(row["next_statuses"])}
        for row in db.execute(
            """SELECT s.code,COALESCE(o.label,s.label) label,COALESCE(o.next_statuses,s.next_statuses) next_statuses
        FROM statuses s LEFT JOIN status_overrides o ON o.code=s.code AND o.municipality_id=?
        WHERE s.code IN ('draft','submitted','under_review','approved','issued','closed') OR o.code IS NOT NULL""",
            (municipality_id,),
        )
    ]


@router.get("/config")
def config(user=Depends(current_user)):
    with connect() as db:
        return {
            "permit_types": [dict(x) for x in db.execute("SELECT * FROM permit_types")],
            "statuses": status_definitions(db, user["municipality_id"]),
            "municipalities": [
                dict(x) for x in db.execute("SELECT * FROM municipalities ORDER BY name")
            ],
            "users": [
                dict(x)
                for x in db.execute(
                    "SELECT id,name,role,municipality_id FROM users WHERE municipality_id=?",
                    (user["municipality_id"],),
                )
            ],
        }


@router.get("/permits")
def permits(
    q: str = Query("", max_length=200),
    status: str = "",
    type: str = "",
    sort: Literal[
        "updated_at",
        "created_at",
        "number",
        "work_address",
        "fee_cents",
        "status",
        "applicant_name",
        "balance_cents",
    ] = "updated_at",
    direction: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user=Depends(current_user),
):
    where, args = scope(user)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where += " AND (p.number LIKE ? ESCAPE '\\' COLLATE NOCASE OR p.work_address LIKE ? ESCAPE '\\' COLLATE NOCASE OR a.name LIKE ? ESCAPE '\\' COLLATE NOCASE OR p.description LIKE ? ESCAPE '\\' COLLATE NOCASE)"
        args.extend([f"%{escaped}%"] * 4)
    if status:
        where += " AND p.status=?"
        args.append(status)
    if type:
        where += " AND p.type=?"
        args.append(type)
    order = sort if sort in ("applicant_name", "balance_cents") else f"p.{sort}"
    with connect() as db:
        total = db.execute(
            "SELECT COUNT(*) FROM permits p JOIN applicants a ON a.id=p.applicant_id WHERE "
            + where,
            args,
        ).fetchone()[0]
        items = db.execute(
            SELECT_PERMIT
            + f" WHERE {where} ORDER BY {order} {direction}, p.id DESC LIMIT ? OFFSET ?",
            args + [page_size, (page - 1) * page_size],
        ).fetchall()
        return {
            "items": [dict(x) for x in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


@router.get("/permits/{permit_id}")
def get_detail(permit_id: int, user=Depends(current_user)):
    with connect() as db:
        return detail(db, permit_id, user)


@router.post("/permits", status_code=201)
def create_permit(body: PermitInput, user=Depends(current_user)):
    require_roles(user, "admin", "clerk", "applicant")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        validate_parties(db, user["municipality_id"], body.applicant_id, body.contractor_id, user)
        assessment = fee(db, body.type, body.area_sqft, user["municipality_id"], body.use_group)
        assessed = assessment["fee_cents"]
        applicant = db.execute(
            "SELECT email FROM applicants WHERE id=?", (body.applicant_id,)
        ).fetchone()
        owner = db.execute(
            "SELECT id FROM users WHERE municipality_id=? AND role='applicant' AND lower(email)=lower(?)",
            (user["municipality_id"], applicant["email"]),
        ).fetchone()
        owner_id = owner["id"] if owner else user["id"]
        stamp = now()
        number = f"DEMO-{stamp[:4]}-{uuid.uuid4().hex[:8].upper()}"
        cursor = db.execute(
            """INSERT INTO permits(number,municipality_id,owner_id,applicant_id,contractor_id,type,status,description,work_address,area_sqft,prior_approval,fee_cents,exempt,exemption_reason,created_at,updated_at)
            VALUES(?,?,?,?,?,?, 'draft', ?,?,?,?,?,0,'',?,?)""",
            (
                number,
                user["municipality_id"],
                owner_id,
                body.applicant_id,
                body.contractor_id,
                body.type,
                body.description,
                body.work_address,
                body.area_sqft,
                int(body.prior_approval),
                assessed,
                stamp,
                stamp,
            ),
        )
        permit_id = cursor.lastrowid
        db.execute(
            "UPDATE permits SET use_group=?,assessed_schedule_id=? WHERE id=?",
            (body.use_group, assessment["schedule_id"], permit_id),
        )
        audit(db, user, "permit", permit_id, "created", {"number": number, "fee_cents": assessed})
        return detail(db, permit_id, user)


@router.patch("/permits/{permit_id}")
def edit_permit(permit_id: int, body: PermitPatch, user=Depends(current_user)):
    require_roles(user, "admin", "clerk", "applicant")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "Provide at least one field to update.")
    if any(value is None and key != "contractor_id" for key, value in changes.items()):
        raise HTTPException(422, "Only contractor may be empty.")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        old = dict(get_permit(db, permit_id, user))
        if old["status"] not in ("draft", "submitted", "under_review") or (
            user["role"] == "applicant" and old["status"] != "draft"
        ):
            raise HTTPException(
                409, "Only editable applications may be changed; applicants may edit drafts only."
            )
        merged = {**old, **changes}
        validate_parties(
            db, old["municipality_id"], merged["applicant_id"], merged["contractor_id"], user
        )
        assessed = old["fee_cents"]
        if any(
            key in changes and changes[key] != old[key]
            for key in ("type", "area_sqft", "use_group")
        ):
            assessment = fee(
                db, merged["type"], merged["area_sqft"], old["municipality_id"], merged["use_group"]
            )
            assessed = 0 if old["exempt"] else assessment["fee_cents"]
            changes["assessed_schedule_id"] = assessment["schedule_id"]
        paid = db.execute(
            "SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE permit_id=?", (permit_id,)
        ).fetchone()[0]
        if assessed < paid:
            raise HTTPException(
                409,
                "The new fee is below payments received. Refund processing requires a separate approved workflow.",
            )
        if "applicant_id" in changes:
            applicant = db.execute(
                "SELECT email FROM applicants WHERE id=?", (merged["applicant_id"],)
            ).fetchone()
            owner = db.execute(
                "SELECT id FROM users WHERE municipality_id=? AND role='applicant' AND lower(email)=lower(?)",
                (old["municipality_id"], applicant["email"]),
            ).fetchone()
            changes["owner_id"] = owner["id"] if owner else user["id"]
        # Field edits are audited separately from status/payment timestamps.
        changes["fee_cents"] = assessed
        changes["updated_at"] = now()
        db.execute(
            "UPDATE permits SET " + ",".join(f"{key}=?" for key in changes) + " WHERE id=?",
            [*changes.values(), permit_id],
        )
        audit(
            db,
            user,
            "permit",
            permit_id,
            "updated",
            {"fields": list(changes), "fee_cents": assessed},
        )
        return detail(db, permit_id, user)


@router.post("/permits/{permit_id}/status")
def change_status(permit_id: int, body: StatusInput, user=Depends(current_user)):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        permit = get_permit(db, permit_id, user)
        if user["role"] == "applicant":
            if permit["status"] != "draft" or body.status != "submitted":
                raise HTTPException(403, "Applicants may submit their own drafts only.")
        elif user["role"] == "reviewer":
            if body.status not in ("under_review", "approved"):
                raise HTTPException(403, "Reviewers may start or approve reviews only.")
        else:
            require_roles(user, "admin", "clerk")
        state = next(
            (
                row
                for row in status_definitions(db, user["municipality_id"])
                if row["code"] == permit["status"]
            ),
            None,
        )
        if not state or body.status not in state["next_statuses"]:
            raise HTTPException(409, "That status transition is not allowed.")
        if body.status != "draft" and not permit["prior_approval"]:
            raise HTTPException(409, "Record prior approval before advancing this application.")
        if body.status in ("approved", "issued", "closed"):
            review = db.execute(
                "SELECT * FROM plan_reviews WHERE permit_id=? ORDER BY id DESC LIMIT 1",
                (permit_id,),
            ).fetchone()
            last_edit = db.execute(
                "SELECT created_at FROM audit_log WHERE entity='permit' AND entity_id=? AND action IN ('created','updated') ORDER BY id DESC LIMIT 1",
                (permit_id,),
            ).fetchone()
            if (
                not review
                or review["result"] != "approved"
                or (last_edit and review["created_at"] < last_edit["created_at"])
            ):
                raise HTTPException(
                    409, "An approved plan review after the last application edit is required."
                )
        if body.status in ("issued", "closed"):
            paid = db.execute(
                "SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE permit_id=?", (permit_id,)
            ).fetchone()[0]
            if paid != permit["fee_cents"]:
                raise HTTPException(409, "Pay the balance in full before issuance.")
        if body.status == "closed":
            last = db.execute(
                "SELECT result FROM inspections WHERE permit_id=? ORDER BY id DESC LIMIT 1",
                (permit_id,),
            ).fetchone()
            if not last or last["result"] != "passed":
                raise HTTPException(409, "The latest inspection must pass before closure.")
        db.execute(
            "UPDATE permits SET status=?,updated_at=? WHERE id=?", (body.status, now(), permit_id)
        )
        audit(
            db,
            user,
            "permit",
            permit_id,
            "status_changed",
            {"from": permit["status"], "to": body.status},
        )
        return detail(db, permit_id, user)


@router.post("/permits/{permit_id}/exemption")
def exemption(permit_id: int, body: ExemptionInput, user=Depends(current_user)):
    require_roles(user, "admin", "clerk")
    if body.exempt and len(body.reason.strip()) < 5:
        raise HTTPException(422, "Provide an exemption reason of at least 5 characters.")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        permit = get_permit(db, permit_id, user)
        if permit["status"] in ("issued", "closed"):
            raise HTTPException(409, "Fees on issued or closed permits cannot be changed.")
        if db.execute("SELECT 1 FROM payments WHERE permit_id=?", (permit_id,)).fetchone():
            raise HTTPException(
                409,
                "A paid application requires an approved refund workflow before changing exemption.",
            )
        assessment = (
            None
            if body.exempt
            else fee(
                db,
                permit["type"],
                permit["area_sqft"],
                permit["municipality_id"],
                permit["use_group"],
            )
        )
        assessed = 0 if body.exempt else assessment["fee_cents"]
        db.execute(
            "UPDATE permits SET exempt=?,exemption_reason=?,fee_cents=?,assessed_schedule_id=? WHERE id=?",
            (
                int(body.exempt),
                body.reason,
                assessed,
                permit["assessed_schedule_id"] if body.exempt else assessment["schedule_id"],
                permit_id,
            ),
        )
        audit(
            db,
            user,
            "permit",
            permit_id,
            "exemption_changed",
            {"exempt": body.exempt, "reason": body.reason, "fee_cents": assessed},
        )
        return detail(db, permit_id, user)


@router.post("/permits/{permit_id}/transfer")
def transfer(permit_id: int, body: TransferInput, user=Depends(current_user)):
    require_roles(user, "admin")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        permit = get_permit(db, permit_id, user)
        if body.municipality_id == user["municipality_id"]:
            raise HTTPException(422, "Select a different destination municipality.")
        if (
            permit["status"] not in ("draft", "submitted")
            or db.execute("SELECT 1 FROM payments WHERE permit_id=?", (permit_id,)).fetchone()
            or db.execute("SELECT 1 FROM plan_reviews WHERE permit_id=?", (permit_id,)).fetchone()
            or db.execute("SELECT 1 FROM inspections WHERE permit_id=?", (permit_id,)).fetchone()
        ):
            raise HTTPException(
                409,
                "Only drafts/submitted applications without payments, reviews or inspections may transfer.",
            )
        validate_parties(db, body.municipality_id, body.applicant_id, body.contractor_id)
        dest = db.execute(
            "SELECT u.id FROM users u JOIN applicants a ON lower(a.email)=lower(u.email) WHERE a.id=? AND u.municipality_id=?",
            (body.applicant_id, body.municipality_id),
        ).fetchone()
        if dest is None:
            dest = db.execute(
                "SELECT id FROM users WHERE municipality_id=? AND role='admin' ORDER BY id LIMIT 1",
                (body.municipality_id,),
            ).fetchone()
        if dest is None:
            raise HTTPException(
                409, "Destination needs a provisioned applicant or municipality administrator."
            )
        assessment = fee(
            db, permit["type"], permit["area_sqft"], body.municipality_id, permit["use_group"]
        )
        if permit["exempt"]:
            raise HTTPException(409, "Remove source municipality exemption before transferring.")
        db.execute(
            "UPDATE permits SET fee_cents=?,assessed_schedule_id=? WHERE id=?",
            (assessment["fee_cents"], assessment["schedule_id"], permit_id),
        )
        db.execute(
            "UPDATE permits SET municipality_id=?,applicant_id=?,contractor_id=?,owner_id=?,status='draft',prior_approval=0,updated_at=? WHERE id=?",
            (
                body.municipality_id,
                body.applicant_id,
                body.contractor_id,
                dest["id"],
                now(),
                permit_id,
            ),
        )
        audit(
            db,
            user,
            "permit",
            permit_id,
            "transferred",
            {"from": user["municipality_id"], "to": body.municipality_id, "owner_id": dest["id"]},
        )
        destination_user = {**user, "municipality_id": body.municipality_id}
        audit(
            db,
            destination_user,
            "permit",
            permit_id,
            "transfer_received",
            {"from": user["municipality_id"], "owner_id": dest["id"]},
        )
        return {
            "id": permit_id,
            "municipality_id": body.municipality_id,
            "message": "Transferred as a draft. Destination staff must verify approvals.",
        }


@router.get("/applicants")
def applicants(user=Depends(current_user)):
    with connect() as db:
        sql, args = "SELECT * FROM applicants WHERE municipality_id=?", [user["municipality_id"]]
        if user["role"] == "applicant":
            sql += " AND lower(email)=lower(?)"
            args.append(user["email"])
        return [dict(x) for x in db.execute(sql + " ORDER BY name", args)]


@router.post("/applicants", status_code=201)
def create_applicant(body: ApplicantInput, user=Depends(current_user)):
    require_roles(user, "admin", "clerk")
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO applicants(municipality_id,name,email,phone) VALUES(?,?,?,?)",
            (user["municipality_id"], body.name, body.email, body.phone),
        )
        audit(db, user, "applicant", cursor.lastrowid, "created", {"name": body.name})
        return dict(
            db.execute("SELECT * FROM applicants WHERE id=?", (cursor.lastrowid,)).fetchone()
        )


@router.get("/contractors")
def contractors(user=Depends(current_user)):
    with connect() as db:
        return [
            dict(x)
            for x in db.execute(
                "SELECT * FROM contractors WHERE municipality_id=? ORDER BY name",
                (user["municipality_id"],),
            )
        ]


@router.post("/contractors", status_code=201)
def create_contractor(body: ContractorInput, user=Depends(current_user)):
    require_roles(user, "admin", "clerk")
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO contractors(municipality_id,name,license_number,email) VALUES(?,?,?,?)",
            (user["municipality_id"], body.name, body.license_number, body.email),
        )
        audit(db, user, "contractor", cursor.lastrowid, "created", {"name": body.name})
        return dict(
            db.execute("SELECT * FROM contractors WHERE id=?", (cursor.lastrowid,)).fetchone()
        )


@router.get("/municipalities")
def municipalities(user=Depends(current_user)):
    with connect() as db:
        return [dict(x) for x in db.execute("SELECT * FROM municipalities ORDER BY name")]


@router.get("/statuses")
def statuses(user=Depends(current_user)):
    with connect() as db:
        return status_definitions(db, user["municipality_id"])


@router.post("/statuses")
def update_status(body: StatusConfig, user=Depends(current_user)):
    require_roles(user, "admin")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        known = {row["code"] for row in status_definitions(db, user["municipality_id"])}
        if any(code not in known and code != body.code for code in body.next_statuses):
            raise HTTPException(422, "All target statuses must exist in your municipality.")
        db.execute(
            "INSERT OR IGNORE INTO statuses(code,label,next_statuses) VALUES(?,?,?)",
            (body.code, body.label, "[]"),
        )
        db.execute(
            "INSERT INTO status_overrides(municipality_id,code,label,next_statuses) VALUES(?,?,?,?) ON CONFLICT(municipality_id,code) DO UPDATE SET label=excluded.label,next_statuses=excluded.next_statuses",
            (user["municipality_id"], body.code, body.label, json.dumps(body.next_statuses)),
        )
        audit(db, user, "status", 0, "configured", body.model_dump())
        return body.model_dump()


@router.get("/dashboard")
def dashboard(user=Depends(current_user)):
    where, args = scope(user)
    with connect() as db:
        items = [
            dict(x)
            for x in db.execute(
                SELECT_PERMIT + " WHERE " + where + " ORDER BY p.updated_at DESC,p.id DESC", args
            )
        ]
        due = db.execute(
            "SELECT COUNT(*) FROM inspections i JOIN permits p ON p.id=i.permit_id WHERE "
            + where
            + " AND i.status='scheduled'",
            args,
        ).fetchone()[0]
        return {
            "permit_count": len(items),
            "open_count": sum(x["status"] != "closed" for x in items),
            "outstanding_cents": sum(x["balance_cents"] for x in items),
            "inspections_due": due,
            "recent_permits": items[:5],
        }
