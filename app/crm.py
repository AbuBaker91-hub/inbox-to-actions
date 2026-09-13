"""CRM writes: upsert contact, upsert deal by reference, insert activity.
Every write is wrapped in idempotency.once keyed on (message_id, action), so
re-processing an email or double-clicking Approve can never write twice."""

import psycopg
from aiforge_core.idempotency import key, once
from psycopg.types.json import Jsonb


def upsert_contact(
    conn: psycopg.Connection,
    email: str,
    name: str | None,
    phone: str | None,
    source_email_id: int | None,
) -> int:
    row = conn.execute(
        """INSERT INTO contacts (email, name, phone, source_email_id)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (email) DO UPDATE SET
               name  = COALESCE(EXCLUDED.name, contacts.name),
               phone = COALESCE(EXCLUDED.phone, contacts.phone)
           RETURNING id""",
        (email.lower(), name, phone, source_email_id),
    ).fetchone()
    return row[0]


def upsert_deal(
    conn: psycopg.Connection,
    contact_id: int,
    reference: str,
    amount: float | None,
    stage: str,
    key_dates: dict | None,
) -> int:
    row = conn.execute(
        """INSERT INTO deals (contact_id, reference, amount, stage, key_dates_json)
           VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (reference) DO UPDATE SET
               amount         = COALESCE(EXCLUDED.amount, deals.amount),
               stage          = EXCLUDED.stage,
               key_dates_json = COALESCE(EXCLUDED.key_dates_json, deals.key_dates_json)
           RETURNING id""",
        (contact_id, reference, amount, stage, Jsonb(key_dates) if key_dates else None),
    ).fetchone()
    return row[0]


def insert_activity(
    conn: psycopg.Connection,
    contact_id: int | None,
    deal_id: int | None,
    kind: str,
    note: str,
) -> int:
    row = conn.execute(
        "INSERT INTO activities (contact_id, deal_id, kind, note) VALUES (%s, %s, %s, %s) RETURNING id",
        (contact_id, deal_id, kind, note),
    ).fetchone()
    return row[0]


def apply(
    conn: psycopg.Connection,
    category: str,
    message_id: str,
    email_row_id: int,
    sender: str,
    payload: dict,
) -> str:
    """Run the act step for a validated (or human-approved) payload. Idempotent."""
    if category == "lead":
        return apply_lead(conn, message_id, email_row_id, payload)
    if category == "document":
        return apply_document(conn, message_id, email_row_id, sender, payload)
    raise ValueError(f"no CRM action for category {category!r}")


def apply_lead(conn: psycopg.Connection, message_id: str, email_row_id: int, payload: dict) -> str:
    contact_id, wrote_contact = once(
        conn,
        key(message_id, "contact"),
        lambda: upsert_contact(
            conn, payload["email"], payload.get("name"), payload.get("phone"), email_row_id
        ),
    )
    deal_id, wrote_deal = None, False
    if payload.get("reference"):
        deal_id, wrote_deal = once(
            conn,
            key(message_id, "deal"),
            lambda: upsert_deal(conn, contact_id, payload["reference"], None, "new", None),
        )
    note = payload.get("intent") or "New inbound lead"
    _, wrote_activity = once(
        conn,
        key(message_id, "activity"),
        lambda: insert_activity(conn, contact_id, deal_id, "lead_created", note),
    )
    return (
        f"contact={contact_id} deal={deal_id} "
        f"writes={int(wrote_contact) + int(wrote_deal) + int(wrote_activity)}"
    )


def apply_document(
    conn: psycopg.Connection, message_id: str, email_row_id: int, sender: str, payload: dict
) -> str:
    parties = payload.get("parties") or []
    amounts = payload.get("amounts") or []
    contact_id, wrote_contact = once(
        conn,
        key(message_id, "contact"),
        lambda: upsert_contact(conn, sender, parties[0] if parties else None, None, email_row_id),
    )
    deal_id, wrote_deal = None, False
    if payload.get("reference"):
        deal_id, wrote_deal = once(
            conn,
            key(message_id, "deal"),
            lambda: upsert_deal(
                conn,
                contact_id,
                payload["reference"],
                amounts[0] if amounts else None,
                "agreement",
                payload.get("key_dates"),
            ),
        )
    note = f"Agreement {payload.get('reference') or '(no reference)'}: parties={', '.join(parties)}"
    _, wrote_activity = once(
        conn,
        key(message_id, "activity"),
        lambda: insert_activity(conn, contact_id, deal_id, "document_processed", note),
    )
    return (
        f"contact={contact_id} deal={deal_id} "
        f"writes={int(wrote_contact) + int(wrote_deal) + int(wrote_activity)}"
    )
