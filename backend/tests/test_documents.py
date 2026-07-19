import hashlib
import uuid
from pathlib import Path

from sqlmodel import Session

from app.config import settings
from app.models.document import Document


def test_upload_document_returns_id_and_processing_status(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    response = client.post(
        "/documents",
        files={"file": ("policy.md", b"# Vacation Policy\n\nEmployees get 20 days.", "text/markdown")},
    )

    assert response.status_code == 202
    body = response.json()
    assert uuid.UUID(body["id"])
    assert body["filename"] == "policy.md"
    assert body["status"] == "processing"


def test_upload_document_saves_file_and_computes_hash(client, db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    content = b"# Remote Work Policy\n\nUp to 3 days per week."

    response = client.post(
        "/documents",
        files={"file": ("remote.md", content, "text/markdown")},
    )
    document_id = uuid.UUID(response.json()["id"])

    with Session(db_engine) as session:
        document = session.get(Document, document_id)

    assert document is not None
    assert document.file_hash == hashlib.sha256(content).hexdigest()
    assert document.status == "processing"
    assert document.content_type == "text/markdown"
    saved_path = Path(document.file_path)
    assert saved_path.exists()
    assert saved_path.read_bytes() == content


def test_upload_document_row_is_owned_by_the_seed_user(client, db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    from app.seed import SEED_USER_ID

    response = client.post(
        "/documents",
        files={"file": ("a.md", b"content", "text/markdown")},
    )
    document_id = uuid.UUID(response.json()["id"])

    with Session(db_engine) as session:
        document = session.get(Document, document_id)

    assert document.user_id == SEED_USER_ID


def test_upload_document_rejects_files_over_the_size_limit(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)
    oversized = b"x" * (2 * 1024 * 1024)

    response = client.post(
        "/documents",
        files={"file": ("big.txt", oversized, "text/plain")},
    )

    assert response.status_code == 413
    assert list(Path(tmp_path).iterdir()) == []
