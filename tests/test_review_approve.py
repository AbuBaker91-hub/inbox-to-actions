"""Approving a review item writes the edited payload exactly once; a second
approve returns 200 and writes nothing (status guard + idempotency keys)."""

from fastapi.testclient import TestClient

from app.main import create_application
from app.worker import ingest_folders
from tests.helpers import LEAD_PAYLOAD, count, write_email


def test_approve_writes_once(test_db, mock_provider, mock_router, tmp_path):
    folder = write_email(tmp_path / "inbox")
    mock_provider.set("classify", {"category": "lead", "confidence": 0.9})
    mock_provider.set("extract_lead", {**LEAD_PAYLOAD, "phone": "5551-02"})  # 6 digits: invalid

    ingest_folders(test_db, mock_router, [folder])
    assert count(test_db, "contacts") == 0  # went to review, nothing written

    app = create_application(
        router=mock_router, conn_factory=lambda: test_db, start_timer=False
    )
    with TestClient(app) as client:
        pending = client.get("/review").json()
        assert len(pending) == 1
        review_id = pending[0]["id"]
        edited = {**pending[0]["payload"], "phone": "+1 202 555 0114"}

        first = client.post(f"/review/{review_id}/approve", json=edited)
        assert first.status_code == 200
        assert first.json()["written"] is True
        assert count(test_db, "contacts") == 1
        assert count(test_db, "activities") == 1
        phone = test_db.execute("SELECT phone FROM contacts").fetchone()[0]
        assert phone == "+1 202 555 0114"

        second = client.post(f"/review/{review_id}/approve", json=edited)
        assert second.status_code == 200
        assert second.json()["written"] is False
        assert count(test_db, "contacts") == 1
        assert count(test_db, "activities") == 1
        assert client.get("/review").json() == []
