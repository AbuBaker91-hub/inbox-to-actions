"""A document whose closing date precedes its acceptance date is never
written; it goes to review with reason 'date_order'."""

from app.validate import validate
from app.worker import ingest_folders
from tests.helpers import DOC_PAYLOAD_BAD_DATES, DOC_PAYLOAD_OK, count, email_status, write_email


def test_closing_before_acceptance_goes_to_review(test_db, mock_provider, mock_router, tmp_path):
    folder = write_email(
        tmp_path / "inbox",
        "doc.txt",
        message_id="test-doc-1",
        sender="legal@northpier.example.com",
        subject="Signed agreement NPX-500",
        body="Agreement attached for recording.",
    )
    mock_provider.set("classify", {"category": "document", "confidence": 0.9})
    mock_provider.set("extract_document", DOC_PAYLOAD_BAD_DATES)

    ingest_folders(test_db, mock_router, [folder])

    rows = test_db.execute("SELECT reason, status FROM review_queue").fetchall()
    assert rows == [("date_order", "pending")]
    assert count(test_db, "deals") == 0
    assert email_status(test_db, "test-doc-1") == "review"


def test_ordered_dates_pass_validation(test_db):
    assert validate(test_db, "document", 0.9, DOC_PAYLOAD_OK) == []
    assert validate(test_db, "document", 0.9, DOC_PAYLOAD_BAD_DATES) == ["date_order"]
