"""Classifier confidence below 0.8 sends the item to review; 0.9 writes."""

from app.worker import ingest_folders
from tests.helpers import LEAD_PAYLOAD, count, email_status, write_email


def test_low_confidence_reviews_high_confidence_writes(
    test_db, mock_provider, mock_router, tmp_path
):
    folder = tmp_path / "inbox"
    write_email(folder, "a-low.txt", message_id="test-low-1", sender="pat.low@example.com")
    write_email(folder, "b-high.txt", message_id="test-high-1", sender="alex.morgan@example.com")
    low_payload = {**LEAD_PAYLOAD, "name": "Pat Low", "email": "pat.low@example.com",
                   "reference": None}
    mock_provider.set(
        "classify",
        [{"category": "lead", "confidence": 0.6}, {"category": "lead", "confidence": 0.9}],
    )
    mock_provider.set("extract_lead", [low_payload, LEAD_PAYLOAD])

    ingest_folders(test_db, mock_router, [folder])

    assert email_status(test_db, "test-low-1") == "review"
    rows = test_db.execute("SELECT reason FROM review_queue").fetchall()
    assert rows == [("low_confidence",)]

    assert email_status(test_db, "test-high-1") == "written"
    assert count(test_db, "contacts") == 1
    contact = test_db.execute("SELECT email FROM contacts").fetchone()
    assert contact[0] == "alex.morgan@example.com"
