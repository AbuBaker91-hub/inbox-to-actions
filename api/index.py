"""Vercel Python serverless entrypoint: exposes the module-level ASGI `app`.

Serverless-safe startup:
- repo root goes on sys.path so `app.*` and `tests.canned` (mock mode) import
- migrations run idempotently at cold start (fast no-op once applied)
- the background ingest timer is disabled when running on Vercel; the demo DB
  is seeded once from a workstation with `python -m app.bootstrap`, and the
  UI's "Run ingest" button (POST /ingest/run) still works per-request
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aiforge_core.db import connect, run_migrations  # noqa: E402

from app.main import create_application  # noqa: E402


def _migrate_idempotently() -> None:
    try:
        conn = connect()
        run_migrations(conn, str(ROOT / "migrations"))
        conn.close()
    except Exception as e:  # don't kill the import; requests will surface DB errors
        print(f"cold-start migration check failed: {e}")


_migrate_idempotently()

app = create_application(start_timer=not os.getenv("VERCEL"))
