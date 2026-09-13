"""Provider 1 times out, provider 2 answers, and the audit trail records
which provider actually produced the output."""

from aiforge_core import audit
from aiforge_core.llm import Router
from aiforge_core.llm.providers import MockProvider, ProviderTimeout

from app.worker import ingest_folders
from tests.helpers import LEAD_PAYLOAD, count, email_status, write_email


def test_provider_fallback_is_used_and_audited(test_db, prompts_dir, tmp_path):
    primary = MockProvider(
        {
            "classify": ProviderTimeout("primary is down"),
            "extract_lead": ProviderTimeout("primary is down"),
        }
    )
    primary.name = "mock-primary"
    fallback = MockProvider(
        {
            "classify": {"category": "lead", "confidence": 0.9},
            "extract_lead": LEAD_PAYLOAD,
        }
    )
    fallback.name = "mock-fallback"
    router = Router([primary, fallback], prompts_dir=prompts_dir, timeout_s=5.0)

    folder = write_email(tmp_path / "inbox")
    ingest_folders(test_db, router, [folder])

    assert primary.calls, "primary provider was tried first"
    assert email_status(test_db, "test-lead-1") == "written"
    assert count(test_db, "contacts") == 1

    classify_rows = [r for r in audit.rows_for(test_db, "test-lead-1") if r["stage"] == "classify"]
    assert classify_rows and "provider=mock-fallback" in classify_rows[0]["detail"]
