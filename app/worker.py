"""The pipeline: ingest -> classify -> extract -> validate -> act.

Runs once per new email file found in the sample folder or the drop folder.
Every stage writes one audit row keyed by the email's message_id, all model
calls go through Router.generate_json with a Pydantic schema, and every CRM
write goes through idempotency.once (see app/crm.py)."""

import email as email_lib
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime
from email import policy
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

import psycopg
from aiforge_core import audit
from aiforge_core.llm import AllProvidersFailed, Router, ValidationFailed
from psycopg.types.json import Jsonb
from pypdf import PdfReader

from app import crm, validate
from app.schemas import Classification, DocumentRecord, LeadRecord

log = logging.getLogger("aiforge")

EMAIL_SUFFIXES = {".eml", ".txt"}


@dataclass
class ParsedEmail:
    message_id: str
    subject: str
    sender: str
    received_at: datetime | None
    body_text: str
    attachments: list[tuple[str, str]] = field(default_factory=list)  # (filename, text)


def pdf_to_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


def parse_email_file(path: Path) -> ParsedEmail:
    """Parse a .eml or headers+body .txt file. PDF attachments are either MIME
    parts or sibling files named in an X-Attachment header."""
    msg = email_lib.message_from_bytes(path.read_bytes(), policy=policy.default)
    message_id = (msg.get("Message-ID") or "").strip().strip("<>") or path.name
    sender = parseaddr(msg.get("From", ""))[1]
    received_at = None
    if msg.get("Date"):
        try:
            received_at = parsedate_to_datetime(msg["Date"])
        except (TypeError, ValueError):
            received_at = None

    body = ""
    body_part = msg.get_body(preferencelist=("plain",))
    if body_part is not None:
        body = body_part.get_content()

    attachments: list[tuple[str, str]] = []
    for part in msg.iter_attachments():
        filename = part.get_filename() or "attachment"
        payload = part.get_payload(decode=True) or b""
        if filename.lower().endswith(".pdf"):
            attachments.append((filename, pdf_to_text(payload)))
        else:
            attachments.append((filename, payload.decode("utf-8", errors="replace")))
    for name in (msg.get("X-Attachment") or "").split(","):
        name = name.strip()
        if not name:
            continue
        sibling = path.parent / name
        if sibling.is_file() and sibling.suffix.lower() == ".pdf":
            attachments.append((name, pdf_to_text(sibling.read_bytes())))

    return ParsedEmail(
        message_id=message_id,
        subject=msg.get("Subject", "").strip(),
        sender=sender,
        received_at=received_at,
        body_text=body.strip(),
        attachments=attachments,
    )


def ingest_folders(conn: psycopg.Connection, router: Router, folders: list[str | Path]) -> int:
    """Process every email file not seen before (by message_id). Returns the
    number of newly processed emails; a second run over the same files is 0."""
    processed = 0
    for folder in folders:
        folder = Path(folder)
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in EMAIL_SUFFIXES:
                continue
            parsed = parse_email_file(path)
            seen = conn.execute(
                "SELECT 1 FROM emails WHERE message_id = %s", (parsed.message_id,)
            ).fetchone()
            if seen:
                continue
            process_email(conn, router, parsed)
            processed += 1
    return processed


def _insert_extraction(
    conn: psycopg.Connection,
    email_id: int,
    category: str,
    confidence: float,
    payload: dict,
    prompt_version: str,
) -> int:
    row = conn.execute(
        """INSERT INTO extractions (email_id, category, confidence, payload_json, prompt_version)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (email_id, category, confidence, Jsonb(payload), prompt_version),
    ).fetchone()
    return row[0]


def _queue_review(conn: psycopg.Connection, email_id: int, extraction_id: int, reason: str) -> None:
    conn.execute(
        "INSERT INTO review_queue (extraction_id, reason) VALUES (%s, %s)",
        (extraction_id, reason),
    )
    _set_status(conn, email_id, "review")


def _set_status(conn: psycopg.Connection, email_id: int, status: str) -> None:
    conn.execute("UPDATE emails SET status = %s WHERE id = %s", (status, email_id))


def process_email(conn: psycopg.Connection, router: Router, parsed: ParsedEmail) -> None:
    mid = parsed.message_id
    email_id = conn.execute(
        """INSERT INTO emails (message_id, subject, sender, received_at, body_text, status)
           VALUES (%s, %s, %s, %s, %s, 'new') RETURNING id""",
        (mid, parsed.subject, parsed.sender, parsed.received_at, parsed.body_text),
    ).fetchone()[0]
    for filename, text in parsed.attachments:
        conn.execute(
            "INSERT INTO attachments (email_id, filename, text) VALUES (%s, %s, %s)",
            (email_id, filename, text),
        )
    audit.record(
        conn,
        "ingest",
        ref=mid,
        input_hash=audit.input_hash(parsed.body_text),
        ok=True,
        detail=f"parsed {parsed.subject!r} with {len(parsed.attachments)} attachment(s)",
    )

    email_text = f"Subject: {parsed.subject}\nFrom: {parsed.sender}\n\n{parsed.body_text}"

    # -- classify -------------------------------------------------------------
    try:
        cls_result = router.generate_json("classify", {"email": email_text}, Classification)
    except ValidationFailed as e:
        audit.record(conn, "classify", ref=mid, ok=False, detail=f"invalid model output: {e}")
        extraction_id = _insert_extraction(conn, email_id, "unknown", 0.0, {}, "classify.v?")
        _queue_review(conn, email_id, extraction_id, "validation")
        return
    except AllProvidersFailed as e:
        audit.record(conn, "classify", ref=mid, ok=False, detail=f"all providers failed: {e}")
        _set_status(conn, email_id, "error")
        return
    category = cls_result.data.category
    confidence = cls_result.data.confidence
    audit.record(
        conn,
        "classify",
        ref=mid,
        input_hash=audit.input_hash(email_text),
        prompt_version=cls_result.prompt_version,
        ok=True,
        detail=f"category={category} confidence={confidence} provider={cls_result.provider}",
    )

    if category in ("status_update", "other"):
        _insert_extraction(conn, email_id, category, confidence, {}, cls_result.prompt_version)
        _set_status(conn, email_id, "skipped")
        return

    # -- extract --------------------------------------------------------------
    prompt_name = "extract_lead" if category == "lead" else "extract_document"
    schema: type = LeadRecord if category == "lead" else DocumentRecord
    variables: dict = {"email": email_text}
    if category == "document":
        variables["attachment_text"] = (
            "\n\n".join(text for _, text in parsed.attachments) or "(no attachment)"
        )
    try:
        ext_result = router.generate_json(prompt_name, variables, schema)
    except ValidationFailed as e:
        audit.record(conn, "extract", ref=mid, ok=False, detail=f"invalid model output: {e}")
        extraction_id = _insert_extraction(
            conn, email_id, category, confidence, {}, f"{prompt_name}.v?"
        )
        _queue_review(conn, email_id, extraction_id, "validation")
        return
    except AllProvidersFailed as e:
        audit.record(conn, "extract", ref=mid, ok=False, detail=f"all providers failed: {e}")
        _set_status(conn, email_id, "error")
        return
    payload = ext_result.data.model_dump()
    extraction_id = _insert_extraction(
        conn, email_id, category, confidence, payload, ext_result.prompt_version
    )
    audit.record(
        conn,
        "extract",
        ref=mid,
        input_hash=audit.input_hash(email_text),
        prompt_version=ext_result.prompt_version,
        ok=True,
        detail=f"fields={sorted(payload)} provider={ext_result.provider}",
    )

    # -- validate -------------------------------------------------------------
    reasons = validate.validate(conn, category, confidence, payload)
    if reasons:
        audit.record(
            conn,
            "validate",
            ref=mid,
            input_hash=audit.input_hash(payload),
            ok=False,
            detail=",".join(reasons),
        )
        _queue_review(conn, email_id, extraction_id, reasons[0])
        return
    audit.record(
        conn,
        "validate",
        ref=mid,
        input_hash=audit.input_hash(payload),
        ok=True,
        detail="all checks passed",
    )

    # -- act ------------------------------------------------------------------
    summary = crm.apply(conn, category, mid, email_id, parsed.sender, payload)
    _set_status(conn, email_id, "written")
    audit.record(conn, "act", ref=mid, ok=True, detail=summary)
