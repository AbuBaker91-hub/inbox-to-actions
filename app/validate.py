"""Deterministic validation of extracted payloads. No model in the loop here:
these rules either pass or send the item to the human review queue.

Reasons (first one becomes the review_queue reason):
    validation       bad email format, bad phone length, unparseable date, bad amount
    date_order       acceptance <= earnest_money <= due_diligence <= closing violated
    contact_conflict same name already in contacts but with a different email
    low_confidence   classifier confidence below 0.8
"""

import re
from datetime import date

import psycopg

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATE_SEQUENCE = ["acceptance", "earnest_money", "due_diligence", "closing"]
CONFIDENCE_THRESHOLD = 0.8
MAX_AMOUNT = 100_000_000


def valid_email(value: str | None) -> bool:
    return bool(value) and bool(EMAIL_RE.match(value))


def valid_phone(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    return 7 <= len(digits) <= 15


def validate(
    conn: psycopg.Connection, category: str, confidence: float, payload: dict
) -> list[str]:
    """Return an ordered, de-duplicated list of problem reasons (empty = ok to write)."""
    reasons: list[str] = []
    if category == "lead":
        reasons += _validate_lead(conn, payload)
    elif category == "document":
        reasons += _validate_document(payload)
    if confidence < CONFIDENCE_THRESHOLD:
        reasons.append("low_confidence")
    return list(dict.fromkeys(reasons))


def _validate_lead(conn: psycopg.Connection, payload: dict) -> list[str]:
    reasons: list[str] = []
    email = payload.get("email")
    if not valid_email(email):
        reasons.append("validation")
    phone = payload.get("phone")
    if phone and not valid_phone(phone):
        reasons.append("validation")
    name = payload.get("name")
    if email and name:
        row = conn.execute(
            "SELECT email FROM contacts WHERE lower(name) = lower(%s)", (name,)
        ).fetchone()
        if row and row[0] and row[0].lower() != email.lower():
            reasons.append("contact_conflict")
    return reasons


def _validate_document(payload: dict) -> list[str]:
    reasons: list[str] = []
    key_dates = payload.get("key_dates") or {}
    parsed: list[date] = []
    parse_failed = False
    for field in DATE_SEQUENCE:
        value = key_dates.get(field)
        if value is None:
            continue
        try:
            parsed.append(date.fromisoformat(value))
        except ValueError:
            reasons.append("validation")
            parse_failed = True
    if not parse_failed and any(a > b for a, b in zip(parsed, parsed[1:], strict=False)):
        reasons.append("date_order")
    for amount in payload.get("amounts") or []:
        if not 0 < amount < MAX_AMOUNT:
            reasons.append("validation")
    return reasons
