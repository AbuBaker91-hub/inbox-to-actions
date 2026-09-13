"""Human review: approve runs the act step with the edited payload through the
same idempotency path as the worker; reject marks the item and leaves an
activity note. Both are safe to call twice."""

import psycopg
from aiforge_core import audit
from aiforge_core.idempotency import key, once
from psycopg.types.json import Jsonb

from app import crm


class ReviewNotFound(Exception):
    pass


def _load(conn: psycopg.Connection, review_id: int) -> dict:
    row = conn.execute(
        """SELECT rq.id, rq.status, rq.extraction_id, x.category, x.payload_json,
                  e.id, e.message_id, e.sender, e.subject
           FROM review_queue rq
           JOIN extractions x ON x.id = rq.extraction_id
           JOIN emails e ON e.id = x.email_id
           WHERE rq.id = %s""",
        (review_id,),
    ).fetchone()
    if row is None:
        raise ReviewNotFound(f"review item {review_id} not found")
    return {
        "id": row[0],
        "status": row[1],
        "extraction_id": row[2],
        "category": row[3],
        "payload": row[4] or {},
        "email_id": row[5],
        "message_id": row[6],
        "sender": row[7],
        "subject": row[8],
    }


def approve(conn: psycopg.Connection, review_id: int, edited_payload: dict | None) -> dict:
    item = _load(conn, review_id)
    if item["status"] != "pending":
        return {"ok": True, "status": item["status"], "written": False}
    payload = edited_payload if edited_payload else item["payload"]
    conn.execute(
        "UPDATE extractions SET payload_json = %s WHERE id = %s",
        (Jsonb(payload), item["extraction_id"]),
    )
    summary = crm.apply(
        conn, item["category"], item["message_id"], item["email_id"], item["sender"], payload
    )
    conn.execute(
        "UPDATE review_queue SET status = 'approved', decided_at = now() WHERE id = %s",
        (review_id,),
    )
    conn.execute("UPDATE emails SET status = 'written' WHERE id = %s", (item["email_id"],))
    audit.record(
        conn,
        "review",
        ref=item["message_id"],
        input_hash=audit.input_hash(payload),
        ok=True,
        detail=f"approved: {summary}",
    )
    return {"ok": True, "status": "approved", "written": True}


def reject(conn: psycopg.Connection, review_id: int, reason: str) -> dict:
    item = _load(conn, review_id)
    if item["status"] != "pending":
        return {"ok": True, "status": item["status"]}
    conn.execute(
        "UPDATE review_queue SET status = 'rejected', decided_at = now() WHERE id = %s",
        (review_id,),
    )
    conn.execute("UPDATE emails SET status = 'skipped' WHERE id = %s", (item["email_id"],))
    note = f"Rejected {item['subject']!r}: {reason or 'no reason given'}"
    once(
        conn,
        key(item["message_id"], "reject_activity"),
        lambda: crm.insert_activity(conn, None, None, "review_rejected", note),
    )
    audit.record(
        conn, "review", ref=item["message_id"], ok=True, detail=f"rejected: {reason}"
    )
    return {"ok": True, "status": "rejected"}
