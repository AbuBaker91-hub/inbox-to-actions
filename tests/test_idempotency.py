"""Processing the same email twice writes exactly one contact, one deal, one
activity — both at the ingest level (message_id seen) and at the CRM write
level (idempotency.once keys)."""

from app import crm
from app.worker import ingest_folders
from tests.helpers import LEAD_PAYLOAD, count, write_email


def test_same_email_twice_writes_once(test_db, mock_provider, mock_router, tmp_path):
    folder = write_email(tmp_path / "inbox")
    mock_provider.set("classify", {"category": "lead", "confidence": 0.9})
    mock_provider.set("extract_lead", LEAD_PAYLOAD)

    assert ingest_folders(test_db, mock_router, [folder]) == 1
    assert ingest_folders(test_db, mock_router, [folder]) == 0  # second run is a no-op

    assert count(test_db, "contacts") == 1
    assert count(test_db, "deals") == 1
    assert count(test_db, "activities") == 1


def test_crm_apply_is_idempotent_at_write_level(test_db, mock_provider, mock_router, tmp_path):
    folder = write_email(tmp_path / "inbox")
    mock_provider.set("classify", {"category": "lead", "confidence": 0.9})
    mock_provider.set("extract_lead", LEAD_PAYLOAD)
    ingest_folders(test_db, mock_router, [folder])

    email_id = test_db.execute(
        "SELECT id FROM emails WHERE message_id = 'test-lead-1'"
    ).fetchone()[0]
    # calling the act step again directly must not write anything new
    crm.apply(test_db, "lead", "test-lead-1", email_id, "alex.morgan@example.com", LEAD_PAYLOAD)

    assert count(test_db, "contacts") == 1
    assert count(test_db, "deals") == 1
    assert count(test_db, "activities") == 1
