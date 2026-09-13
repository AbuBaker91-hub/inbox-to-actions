"""Broken JSON from the model never reaches the CRM: the item lands in the
review queue with reason 'validation' and no contact is written."""

from app.worker import ingest_folders
from tests.helpers import count, email_status, write_email


def test_broken_json_goes_to_review(test_db, mock_provider, mock_router, tmp_path):
    folder = write_email(tmp_path / "inbox")
    mock_provider.set("classify", {"category": "lead", "confidence": 0.9})
    mock_provider.set("extract_lead", "this is {not valid json at all")

    ingest_folders(test_db, mock_router, [folder])

    rows = test_db.execute("SELECT reason, status FROM review_queue").fetchall()
    assert rows == [("validation", "pending")]
    assert count(test_db, "contacts") == 0
    assert count(test_db, "deals") == 0
    assert email_status(test_db, "test-lead-1") == "review"
