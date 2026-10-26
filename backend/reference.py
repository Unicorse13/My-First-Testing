"""Municipal fee schedule setup supported by supplied S-01/S-02 reference guides.

This intentionally limited engine supports explicit demo fixed and per-square-foot
items only. The official UCC template, S-A2 basis chart, current ordinances and DCA
rates were not supplied. Tier/group/state-rate calculations are not fabricated.
"""

import sqlite3
from datetime import date
from html import escape
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .db import connect
from .security import audit, current_user, now, require_roles

router = APIRouter()
STAFF = ("admin", "clerk", "reviewer", "inspector")
Subcode = Literal["building", "electrical", "elevator", "fire_protection", "plumbing"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Item(Input):
    position: int = Field(ge=1, le=500, strict=True)
    description: str = Field(min_length=2, max_length=300)
    basis: Literal["fixed", "per_unit"]
    amount_cents: int = Field(ge=0, le=100000000, strict=True)
    minimum_cents: int = Field(default=0, ge=0, le=100000000, strict=True)


class Schedule(Input):
    subcode: Subcode
    use_group: str = Field(default="", max_length=40)
    effective_date: date
    min_fee_cents: int = Field(default=0, ge=0, le=100000000, strict=True)
    max_fee_cents: int | None = Field(default=None, ge=0, le=100000000, strict=True)
    ordinance_citation: str = Field(min_length=3, max_length=300)
    items: list[Item] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.subcode != "building" and self.use_group:
            raise ValueError("Use-group variants apply only to building schedules.")
        if self.max_fee_cents is not None and self.max_fee_cents < self.min_fee_cents:
            raise ValueError("Maximum fee must be at least the minimum fee.")
        if [item.position for item in self.items] != list(range(1, len(self.items) + 1)):
            raise ValueError("Preserve line-item order using consecutive positions starting at 1.")
        return self


class SchedulePatch(Input):
    effective_date: date | None = None
    min_fee_cents: int | None = Field(default=None, ge=0, le=100000000, strict=True)
    max_fee_cents: int | None = Field(default=None, ge=0, le=100000000, strict=True)
    ordinance_citation: str | None = Field(default=None, min_length=3, max_length=300)


class ItemPatch(Input):
    description: str | None = Field(default=None, min_length=2, max_length=300)
    basis: Literal["fixed", "per_unit"] | None = None
    amount_cents: int | None = Field(default=None, ge=0, le=100000000, strict=True)
    minimum_cents: int | None = Field(default=None, ge=0, le=100000000, strict=True)


class Copy(Input):
    effective_date: date


class Activation(Input):
    confirmed_review: Literal[True]


def scoped(db, ident, user):
    require_roles(user, *STAFF)
    row = db.execute(
        "SELECT * FROM fee_schedules WHERE id=? AND municipality_id=?",
        (ident, user["municipality_id"]),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Fee schedule not found.")
    return row


def result(db, row):
    return {
        **dict(row),
        "items": [
            dict(item)
            for item in db.execute(
                "SELECT * FROM fee_schedule_items WHERE schedule_id=? ORDER BY position",
                (row["id"],),
            )
        ],
    }


def editable(row):
    if row["status"] == "active":
        raise HTTPException(
            409, "Activated schedules are immutable. Copy to a new effective date to change fees."
        )


def insert_item(db, ident, item):
    db.execute(
        "INSERT INTO fee_schedule_items(schedule_id,position,description,basis,amount_cents,minimum_cents) VALUES(?,?,?,?,?,?)",
        (ident, item.position, item.description, item.basis, item.amount_cents, item.minimum_cents),
    )


def conflict(exc):
    if "UNIQUE" in str(exc):
        raise HTTPException(
            409, "A schedule already exists for that subcode, use group and effective date."
        ) from exc
    raise exc


@router.get("/fee-schedules")
def list_schedules(user=Depends(current_user)):
    require_roles(user, *STAFF)
    with connect() as db:
        return [
            result(db, row)
            for row in db.execute(
                "SELECT * FROM fee_schedules WHERE municipality_id=? ORDER BY effective_date DESC,id DESC",
                (user["municipality_id"],),
            )
        ]


@router.get("/fee-schedules/{ident}")
def get_schedule(ident: int, user=Depends(current_user)):
    with connect() as db:
        return result(db, scoped(db, ident, user))


@router.post("/fee-schedules", status_code=201)
def create_schedule(body: Schedule, user=Depends(current_user)):
    require_roles(user, "admin", "clerk")
    try:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                "INSERT INTO fee_schedules(municipality_id,subcode,use_group,effective_date,min_fee_cents,max_fee_cents,ordinance_citation,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    user["municipality_id"],
                    body.subcode,
                    body.use_group,
                    body.effective_date.isoformat(),
                    body.min_fee_cents,
                    body.max_fee_cents,
                    body.ordinance_citation,
                    now(),
                ),
            )
            for item in body.items:
                insert_item(db, cursor.lastrowid, item)
            audit(
                db,
                user,
                "fee_schedule",
                cursor.lastrowid,
                "created",
                {"subcode": body.subcode, "effective_date": body.effective_date.isoformat()},
            )
            return result(db, scoped(db, cursor.lastrowid, user))
    except sqlite3.IntegrityError as exc:
        conflict(exc)


@router.patch("/fee-schedules/{ident}")
def edit_schedule(ident: int, body: SchedulePatch, user=Depends(current_user)):
    require_roles(user, "admin", "clerk")
    changes = body.model_dump(exclude_unset=True, mode="json")
    if not changes or any(
        value is None and key != "max_fee_cents" for key, value in changes.items()
    ):
        raise HTTPException(422, "Supply fields to update. Only maximum fee may be empty.")
    try:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = scoped(db, ident, user)
            editable(old)
            merged = {**dict(old), **changes}
            if (
                merged["max_fee_cents"] is not None
                and merged["max_fee_cents"] < merged["min_fee_cents"]
            ):
                raise HTTPException(422, "Maximum fee must be at least the minimum fee.")
            db.execute(
                "UPDATE fee_schedules SET "
                + ",".join(f"{key}=?" for key in changes)
                + " WHERE id=?",
                [*changes.values(), ident],
            )
            audit(db, user, "fee_schedule", ident, "updated", {"fields": list(changes)})
            return result(db, scoped(db, ident, user))
    except sqlite3.IntegrityError as exc:
        conflict(exc)


@router.post("/fee-schedules/{ident}/items", status_code=201)
def append_item(ident: int, body: Item, user=Depends(current_user)):
    require_roles(user, "admin", "clerk")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        old = scoped(db, ident, user)
        editable(old)
        count = db.execute(
            "SELECT COUNT(*) FROM fee_schedule_items WHERE schedule_id=?", (ident,)
        ).fetchone()[0]
        if body.position != count + 1:
            raise HTTPException(
                422,
                "Append new items at the next consecutive position; existing line-item order is retained.",
            )
        insert_item(db, ident, body)
        audit(db, user, "fee_schedule", ident, "item_appended", {"position": body.position})
        return result(db, scoped(db, ident, user))


@router.patch("/fee-schedules/{ident}/items/{position}")
def edit_item(ident: int, position: int, body: ItemPatch, user=Depends(current_user)):
    require_roles(user, "admin", "clerk")
    changes = body.model_dump(exclude_unset=True)
    if not changes or any(value is None for value in changes.values()):
        raise HTTPException(422, "Supply non-empty item fields to update.")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        old = scoped(db, ident, user)
        editable(old)
        if not db.execute(
            "SELECT id FROM fee_schedule_items WHERE schedule_id=? AND position=?",
            (ident, position),
        ).fetchone():
            raise HTTPException(404, "Line item not found.")
        db.execute(
            "UPDATE fee_schedule_items SET "
            + ",".join(f"{key}=?" for key in changes)
            + " WHERE schedule_id=? AND position=?",
            [*changes.values(), ident, position],
        )
        audit(
            db,
            user,
            "fee_schedule",
            ident,
            "item_updated",
            {"position": position, "fields": list(changes)},
        )
        return result(db, scoped(db, ident, user))


@router.post("/fee-schedules/{ident}/copy", status_code=201)
def copy_schedule(ident: int, body: Copy, user=Depends(current_user)):
    require_roles(user, "admin", "clerk")
    try:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = scoped(db, ident, user)
            if body.effective_date.isoformat() <= old["effective_date"]:
                raise HTTPException(422, "A copied version requires a later effective date.")
            cursor = db.execute(
                "INSERT INTO fee_schedules(municipality_id,subcode,use_group,effective_date,min_fee_cents,max_fee_cents,ordinance_citation,copied_from_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    old["municipality_id"],
                    old["subcode"],
                    old["use_group"],
                    body.effective_date.isoformat(),
                    old["min_fee_cents"],
                    old["max_fee_cents"],
                    old["ordinance_citation"],
                    ident,
                    now(),
                ),
            )
            db.execute(
                "INSERT INTO fee_schedule_items(schedule_id,position,description,basis,amount_cents,minimum_cents) SELECT ?,position,description,basis,amount_cents,minimum_cents FROM fee_schedule_items WHERE schedule_id=? ORDER BY position",
                (cursor.lastrowid, ident),
            )
            audit(
                db,
                user,
                "fee_schedule",
                cursor.lastrowid,
                "copied",
                {"from": ident, "effective_date": body.effective_date.isoformat()},
            )
            return result(db, scoped(db, cursor.lastrowid, user))
    except sqlite3.IntegrityError as exc:
        conflict(exc)


@router.post("/fee-schedules/{ident}/activate")
def activate_schedule(ident: int, body: Activation, user=Depends(current_user)):
    require_roles(user, "admin")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        old = scoped(db, ident, user)
        editable(old)
        if not db.execute(
            "SELECT 1 FROM fee_schedule_items WHERE schedule_id=?", (ident,)
        ).fetchone():
            raise HTTPException(409, "A schedule requires at least one line item.")
        db.execute(
            "UPDATE fee_schedules SET status='active',activated_at=? WHERE id=?", (now(), ident)
        )
        audit(
            db,
            user,
            "fee_schedule",
            ident,
            "activated",
            {"confirmed_printed_and_reviewed": body.confirmed_review},
        )
        return result(db, scoped(db, ident, user))


def calculate_fee(db, municipality_id, subcode, area, as_of, use_group=""):
    """Resolve effective version and calculate explicitly supported demo basis only.

    Per-unit means cents per square foot in this implementation. This is a declared
    demonstration definition, not an inferred mapping to any official UCC basis.
    Returns None if no matching active effective schedule has been configured.
    """
    as_of = as_of.isoformat() if isinstance(as_of, date) else str(as_of)[:10]
    schedule = db.execute(
        "SELECT * FROM fee_schedules WHERE municipality_id=? AND subcode=? AND use_group=? AND status='active' AND effective_date<=? ORDER BY effective_date DESC,id DESC LIMIT 1",
        (municipality_id, subcode, use_group, as_of),
    ).fetchone()
    if not schedule:
        return None
    items = db.execute(
        "SELECT * FROM fee_schedule_items WHERE schedule_id=? ORDER BY position", (schedule["id"],)
    ).fetchall()
    total = sum(
        max(
            item["minimum_cents"],
            item["amount_cents"] * (area if item["basis"] == "per_unit" else 1),
        )
        for item in items
    )
    total = max(total, schedule["min_fee_cents"])
    if schedule["max_fee_cents"] is not None:
        total = min(total, schedule["max_fee_cents"])
    return {"fee_cents": total, "schedule_id": schedule["id"]}


@router.get("/fee-schedules/{ident}/document", response_class=HTMLResponse)
def print_schedule(ident: int, user=Depends(current_user)):
    with connect() as db:
        row = scoped(db, ident, user)
        data = result(db, row)
        municipality = db.execute(
            "SELECT name FROM municipalities WHERE id=?", (user["municipality_id"],)
        ).fetchone()[0]
    rows = "".join(
        f"<tr><td>{item['position']}</td><td>{escape(item['description'])}</td><td>{escape(item['basis'])}</td><td>${item['amount_cents'] / 100:,.2f}</td><td>${item['minimum_cents'] / 100:,.2f}</td></tr>"
        for item in data["items"]
    )
    maximum = "None" if data["max_fee_cents"] is None else f"${data['max_fee_cents'] / 100:,.2f}"
    return HTMLResponse(
        f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Fee schedule {ident}</title>
<style>body{{font:16px system-ui;max-width:1000px;margin:3rem auto;padding:1rem;color:#182337}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccd4df;padding:.7rem;text-align:left}}.banner{{border:2px solid #c06426;padding:1rem}}@media print{{body{{margin:0}}}}</style>
<h1>{escape(municipality)} — {escape(data["subcode"].replace("_", " ").title())}</h1>
<p class="banner">DEMONSTRATION ONLY. No official UCC template or verified municipal rates supplied. Fixed and per-square-foot demo bases only. Print and check this schedule against your worksheet before activation.</p>
<p>Status: {escape(data["status"])}; effective: {escape(data["effective_date"])}; use group: {escape(data["use_group"]) or "Default"}.</p>
<p>Ordinance reference: {escape(data["ordinance_citation"])}</p><p>Minimum: ${data["min_fee_cents"] / 100:,.2f}; maximum: {maximum}</p>
<table><thead><tr><th>Position</th><th>Description</th><th>Demo basis</th><th>Amount</th><th>Item minimum</th></tr></thead><tbody>{rows}</tbody></table>
<p>Activated versions are retained unchanged; amendments require a copied version and new effective date.</p></html>""",
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
        },
    )


REFERENCE_TABLES = [
    (
        "additional_fees",
        "Additional Fees",
        "municipality / DCA-controlled items",
        True,
        "Deferred: DCA preset items, training surcharge and ordinance-supported additions require authoritative rates.",
    ),
    (
        "architects_engineers",
        "Architects / Engineers",
        "municipality",
        False,
        "Deferred: no dedicated professional directory.",
    ),
    (
        "block_lot",
        "Block / Lot",
        "municipality / imported tax data",
        False,
        "Deferred: no tax parcel import or assessor writeback integration.",
    ),
    (
        "contractors",
        "Contractors",
        "municipality",
        False,
        "Demo create/list available; no UCCARS import.",
    ),
    (
        "fee_schedules",
        "Fee Schedules",
        "municipality",
        True,
        "Partial: five subcodes, use-group versions, ordered demo line items, copy, print, review and activation. Official UCC templates and complex bases unavailable.",
    ),
    (
        "inspection_types",
        "Inspection Types",
        "NJDCA",
        False,
        "Deferred: official preloaded values unavailable.",
    ),
    (
        "interlocal_offices",
        "Interlocal Offices",
        "NJDCA",
        False,
        "Deferred: official preloaded values unavailable.",
    ),
    (
        "municipalities",
        "Municipalities",
        "municipality / preloaded basic record",
        True,
        "Demo names only; office, appeals board and official print metadata deferred.",
    ),
    (
        "prior_approvals",
        "Prior Approvals",
        "NJDCA",
        False,
        "Partial: demo boolean approval only; official prior-approval catalog unavailable.",
    ),
    (
        "staff",
        "Staff",
        "municipality",
        True,
        "Partial: provisioned demo roles and inspector assignments; official staff categories and maintenance screens deferred.",
    ),
    (
        "state_offices",
        "State Offices",
        "NJDCA",
        False,
        "Deferred: official preloaded values unavailable.",
    ),
    (
        "use_groups",
        "Use Groups",
        "NJDCA",
        False,
        "Partial: free-text fee-schedule variant; official reference catalog unavailable.",
    ),
    (
        "third_party_agencies",
        "3rd Party Agencies",
        "NJDCA",
        False,
        "Deferred: no agency register or contracted DCA fee-rate integration.",
    ),
]


@router.get("/reference-tables")
def reference_tables(user=Depends(current_user)):
    require_roles(user, *STAFF)
    return {
        "source": "S-01 rev 2007-01-17; S-02 rev 2009-08-15; G-02 rev 2004-08-19",
        "scope": "Reference inventory only. Historical guide descriptions are not verified current regulations.",
        "tables": [
            {
                "code": code,
                "name": name,
                "maintainer": owner,
                "initial_input_required": required,
                "implementation": implementation,
                "can_maintain_demo": user["role"] in ("admin", "clerk")
                and code in ("contractors", "fee_schedules"),
            }
            for code, name, owner, required, implementation in REFERENCE_TABLES
        ],
    }
