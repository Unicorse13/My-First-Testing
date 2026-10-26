"""Session authentication and reusable municipality/ownership guards."""

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request

from .db import connect


def now():
    return datetime.now(timezone.utc).isoformat()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"scrypt${salt}${digest}"


def verify_password(password, encoded):
    try:
        algorithm, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(request: Request):
    token = request.cookies.get("permits_session", "")
    if not token or len(token) > 200:
        raise HTTPException(401, "Sign in to continue.")
    with connect() as db:
        user = db.execute(
            """SELECT u.*, s.csrf_token FROM sessions s JOIN users u ON u.id=s.user_id
                             WHERE s.token_hash=? AND s.expires_at>?""",
            (token_hash(token), now()),
        ).fetchone()
    if user is None:
        raise HTTPException(401, "Your session expired. Please sign in again.")
    return dict(user)


def public_user(user):
    return {key: user[key] for key in ("id", "name", "email", "role", "municipality_id")}


def require_roles(user, *roles):
    if user["role"] not in roles:
        raise HTTPException(403, "Your role does not allow this action.")


def get_permit(db, permit_id, user):
    row = db.execute(
        "SELECT * FROM permits WHERE id=? AND municipality_id=?",
        (permit_id, user["municipality_id"]),
    ).fetchone()
    if row is None or (user["role"] == "applicant" and row["owner_id"] != user["id"]):
        raise HTTPException(404, "Permit not found.")
    return row


def audit(db, user, entity, entity_id, action, details):
    db.execute(
        """INSERT INTO audit_log(municipality_id,user_id,entity,entity_id,action,details,created_at)
                  VALUES(?,?,?,?,?,?,?)""",
        (
            user["municipality_id"],
            user["id"],
            entity,
            entity_id,
            action,
            json.dumps(details, sort_keys=True),
            now(),
        ),
    )


def new_session(db, user):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.execute("DELETE FROM sessions WHERE expires_at<=?", (now(),))
    db.execute(
        "INSERT INTO sessions(token_hash,user_id,csrf_token,expires_at) VALUES(?,?,?,?)",
        (
            token_hash(token),
            user["id"],
            csrf,
            (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
        ),
    )
    return token, csrf


def demo_mode():
    return os.getenv("DEMO_MODE", "false").lower() == "true"
