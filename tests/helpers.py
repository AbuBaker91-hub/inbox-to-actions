"""Small shared helpers for the guardrail tests. No network anywhere."""

from pathlib import Path

LEAD_PAYLOAD = {
    "name": "Alex Morgan",
    "email": "alex.morgan@example.com",
    "phone": "+1 202 555 0114",
    "reference": "ABC-100",
    "intent": "Wants a viewing of listing ABC-100",
}

DOC_PAYLOAD_OK = {
    "parties": ["North Pier LLC", "Harbor Trust"],
    "amounts": [320000.0],
    "key_dates": {
        "acceptance": "2026-09-01",
        "earnest_money": "2026-09-03",
        "due_diligence": "2026-09-10",
        "closing": "2026-09-30",
    },
    "reference": "NPX-500",
}

DOC_PAYLOAD_BAD_DATES = {
    **DOC_PAYLOAD_OK,
    "key_dates": {
        "acceptance": "2026-09-30",
        "earnest_money": "2026-09-03",
        "due_diligence": "2026-09-10",
        "closing": "2026-09-01",
    },
}


def write_email(
    folder: Path,
    filename: str = "lead.txt",
    *,
    message_id: str = "test-lead-1",
    sender: str = "alex.morgan@example.com",
    subject: str = "Interested in listing ABC-100",
    body: str = "Hi, I'd like a viewing this week. Call me on +1 202 555 0114.\n\nAlex Morgan",
) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / filename).write_text(
        f"Message-ID: <{message_id}>\n"
        f"From: {sender}\n"
        f"Subject: {subject}\n"
        "Date: Mon, 07 Sep 2026 09:00:00 +0000\n"
        "\n"
        f"{body}\n",
        encoding="utf-8",
    )
    return folder


def count(conn, table: str) -> int:
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]  # noqa: S608


def email_status(conn, message_id: str) -> str:
    return conn.execute(
        "SELECT status FROM emails WHERE message_id = %s", (message_id,)
    ).fetchone()[0]
