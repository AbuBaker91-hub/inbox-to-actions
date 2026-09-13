"""FastAPI app: the routes from the spec plus a background ingest timer.

Router wiring:
    LLM_PROVIDER_ORDER=gemini,groq   real free-tier chain (needs keys)
    LLM_PROVIDER_ORDER=mock          offline demo: MockProvider preloaded with
                                     tests/canned.py responses, zero keys needed
"""

import asyncio
import contextlib
import logging
import os
from pathlib import Path

from aiforge_core.app import create_app
from aiforge_core.db import connect
from aiforge_core.llm import Router, router_from_env
from aiforge_core.llm.providers import MockProvider
from fastapi import HTTPException
from fastapi.responses import FileResponse

from app import review as review_mod
from app import worker

log = logging.getLogger("aiforge")

ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = ROOT / "prompts"
STATIC_DIR = ROOT / "static"


def build_router() -> Router:
    order = os.getenv("LLM_PROVIDER_ORDER", "gemini,groq").strip()
    if order == "mock":
        from tests.canned import canned_responses

        return Router([MockProvider(canned_responses())], prompts_dir=str(PROMPTS_DIR))
    return router_from_env(str(PROMPTS_DIR))


def inbox_dirs() -> list[str]:
    raw = os.getenv("INBOX_DIRS", f"{ROOT / 'samples' / 'inbox'},{ROOT / 'inbox'}")
    return [p.strip() for p in raw.split(",") if p.strip()]


def create_application(
    router: Router | None = None,
    conn_factory=None,
    start_timer: bool = True,
):
    app = create_app(title="inbox-to-actions", static_dir=str(STATIC_DIR))
    app.state.router = router
    app.state.conn_factory = conn_factory
    app.state.start_timer = start_timer
    app.state.ingest_task = None

    @contextlib.contextmanager
    def db():
        if app.state.conn_factory is not None:
            yield app.state.conn_factory()  # test-injected, caller owns it
        else:
            conn = connect()
            try:
                yield conn
            finally:
                conn.close()

    def get_router() -> Router:
        if app.state.router is None:
            try:
                app.state.router = build_router()
            except Exception as e:
                raise HTTPException(503, f"LLM router not configured: {e}") from e
        return app.state.router

    def run_ingest() -> int:
        with db() as conn:
            return worker.ingest_folders(conn, get_router(), inbox_dirs())

    # -- pages ----------------------------------------------------------------
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    # -- emails ---------------------------------------------------------------
    @app.get("/emails")
    def list_emails():
        with db() as conn:
            rows = conn.execute(
                """SELECT e.id, e.message_id, e.subject, e.sender, e.received_at, e.status,
                          x.category, x.confidence
                   FROM emails e
                   LEFT JOIN LATERAL (
                       SELECT category, confidence FROM extractions
                       WHERE email_id = e.id ORDER BY id DESC LIMIT 1
                   ) x ON true
                   ORDER BY e.id"""
            ).fetchall()
        return [
            {
                "id": r[0],
                "message_id": r[1],
                "subject": r[2],
                "sender": r[3],
                "received_at": r[4].isoformat() if r[4] else None,
                "status": r[5],
                "category": r[6],
                "confidence": r[7],
            }
            for r in rows
        ]

    @app.get("/emails/{email_id}")
    def email_detail(email_id: int):
        from aiforge_core import audit

        with db() as conn:
            e = conn.execute(
                """SELECT id, message_id, subject, sender, received_at, body_text, status
                   FROM emails WHERE id = %s""",
                (email_id,),
            ).fetchone()
            if e is None:
                raise HTTPException(404, "email not found")
            atts = conn.execute(
                "SELECT filename, text FROM attachments WHERE email_id = %s ORDER BY id",
                (email_id,),
            ).fetchall()
            x = conn.execute(
                """SELECT id, category, confidence, payload_json, prompt_version
                   FROM extractions WHERE email_id = %s ORDER BY id DESC LIMIT 1""",
                (email_id,),
            ).fetchone()
            rq = None
            if x is not None:
                rq = conn.execute(
                    "SELECT id, reason, status FROM review_queue WHERE extraction_id = %s",
                    (x[0],),
                ).fetchone()
            audit_rows = audit.rows_for(conn, e[1])
        return {
            "id": e[0],
            "message_id": e[1],
            "subject": e[2],
            "sender": e[3],
            "received_at": e[4].isoformat() if e[4] else None,
            "body_text": e[5],
            "status": e[6],
            "attachments": [{"filename": a[0], "text": a[1]} for a in atts],
            "extraction": None
            if x is None
            else {
                "id": x[0],
                "category": x[1],
                "confidence": x[2],
                "payload": x[3],
                "prompt_version": x[4],
            },
            "review": None if rq is None else {"id": rq[0], "reason": rq[1], "status": rq[2]},
            "audit": audit_rows,
        }

    # -- review queue ---------------------------------------------------------
    @app.get("/review")
    def list_review():
        with db() as conn:
            rows = conn.execute(
                """SELECT rq.id, rq.reason, x.category, x.confidence, x.payload_json,
                          e.id, e.subject, e.sender
                   FROM review_queue rq
                   JOIN extractions x ON x.id = rq.extraction_id
                   JOIN emails e ON e.id = x.email_id
                   WHERE rq.status = 'pending'
                   ORDER BY rq.id"""
            ).fetchall()
        return [
            {
                "id": r[0],
                "reason": r[1],
                "category": r[2],
                "confidence": r[3],
                "payload": r[4],
                "email_id": r[5],
                "subject": r[6],
                "sender": r[7],
            }
            for r in rows
        ]

    @app.post("/review/{review_id}/approve")
    def approve(review_id: int, payload: dict | None = None):
        with db() as conn:
            try:
                return review_mod.approve(conn, review_id, payload or None)
            except review_mod.ReviewNotFound as e:
                raise HTTPException(404, str(e)) from e

    @app.post("/review/{review_id}/reject")
    def reject(review_id: int, body: dict | None = None):
        with db() as conn:
            try:
                return review_mod.reject(conn, review_id, str((body or {}).get("reason", "")))
            except review_mod.ReviewNotFound as e:
                raise HTTPException(404, str(e)) from e

    # -- CRM ------------------------------------------------------------------
    @app.get("/crm/contacts")
    def crm_contacts():
        with db() as conn:
            rows = conn.execute(
                "SELECT id, email, name, phone, source_email_id FROM contacts ORDER BY id"
            ).fetchall()
        return [
            {"id": r[0], "email": r[1], "name": r[2], "phone": r[3], "source_email_id": r[4]}
            for r in rows
        ]

    @app.get("/crm/deals")
    def crm_deals():
        with db() as conn:
            rows = conn.execute(
                "SELECT id, contact_id, reference, amount, stage, key_dates_json FROM deals ORDER BY id"
            ).fetchall()
        return [
            {
                "id": r[0],
                "contact_id": r[1],
                "reference": r[2],
                "amount": float(r[3]) if r[3] is not None else None,
                "stage": r[4],
                "key_dates": r[5],
            }
            for r in rows
        ]

    @app.get("/crm/activities")
    def crm_activities():
        with db() as conn:
            rows = conn.execute(
                """SELECT id, contact_id, deal_id, kind, note, created_at
                   FROM activities ORDER BY id"""
            ).fetchall()
        return [
            {
                "id": r[0],
                "contact_id": r[1],
                "deal_id": r[2],
                "kind": r[3],
                "note": r[4],
                "created_at": r[5].isoformat(),
            }
            for r in rows
        ]

    # -- ingest ---------------------------------------------------------------
    @app.post("/ingest/run")
    def ingest_run():
        return {"processed": run_ingest()}

    # -- background timer (same function as POST /ingest/run) ----------------
    async def ingest_loop(interval_s: float):
        while True:
            await asyncio.sleep(interval_s)
            try:
                n = await asyncio.to_thread(run_ingest)
                if n:
                    log.info("timer ingest processed %d email(s)", n)
            except Exception as e:  # never kill the loop
                log.warning("timer ingest failed: %s", e)

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        interval_s = float(os.getenv("INGEST_INTERVAL_S", "30"))
        if app.state.start_timer and interval_s > 0:
            app.state.ingest_task = asyncio.create_task(ingest_loop(interval_s))
        try:
            yield
        finally:
            if app.state.ingest_task is not None:
                app.state.ingest_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await app.state.ingest_task

    app.router.lifespan_context = lifespan

    return app


app = create_application()
