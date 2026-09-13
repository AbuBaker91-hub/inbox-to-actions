"""Run migrations and (unless --migrate-only) seed the sample inbox.
Used by `make setup`, `make demo` prep and the Docker entrypoint. Idempotent:
migrations are tracked in schema_migrations, seeding skips seen message_ids."""

import sys

from aiforge_core.db import connect, run_migrations

from app.main import ROOT, build_router, inbox_dirs
from app.worker import ingest_folders


def main(migrate_only: bool = False) -> None:
    conn = connect()
    applied = run_migrations(conn, str(ROOT / "migrations"))
    print(f"migrations applied: {applied or 'none (up to date)'}")
    if not migrate_only:
        try:
            router = build_router()
            n = ingest_folders(conn, router, inbox_dirs())
            print(f"seed: processed {n} new email(s)")
        except Exception as e:
            print(f"seed skipped ({e}); POST /ingest/run will process the samples later")
    conn.close()


if __name__ == "__main__":
    main(migrate_only="--migrate-only" in sys.argv)
