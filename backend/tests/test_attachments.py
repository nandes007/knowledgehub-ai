"""Chat attachments in, document images out - through the HTTP API."""

import io
import json
import uuid
from pathlib import Path

import pytest
from PIL import Image
from sqlmodel import Session, select

from app.config import settings
from app.main import app
from app.models.department import Department
from app.models.document import Document
from app.models.message import Message
from app.models.user import User
from app.services import storage
from app.services.llm import TokenUsage, get_llm_provider, message_text
from ingestion.chunk import Chunk
from ingestion.index import VectorStore, get_vector_store
from tests.conftest import _registered_client


class _RecordingLLM:
    """Records the chat messages it receives and streams a scripted answer."""

    def __init__(self, answer: list[str] | None = None) -> None:
        self.calls: list[list[dict]] = []
        self.embedded: list[str] = []
        self.answer = answer or ["ok"]

    def embed_texts(self, texts):
        self.embedded.extend(texts)
        return [[1.0, 0.0] for _ in texts]

    def transcribe_image(self, png: bytes) -> str:
        return "OCR text"

    def generate_answer_stream(self, messages, *, usage: TokenUsage | None = None):
        self.calls.append(messages)
        yield from self.answer


def _png(width=40, height=30) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "red").save(buffer, format="PNG")
    return buffer.getvalue()


def _image_parts(messages) -> list[dict]:
    content = messages[0]["content"]
    return [p for p in content if p["type"] == "image_url"] if isinstance(content, list) else []


def _events(response) -> list[tuple[str, dict]]:
    events = []
    for block in response.text.strip().split("\n\n"):
        lines = block.splitlines()
        event = next(line.removeprefix("event: ") for line in lines if line.startswith("event: "))
        data = next(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
        events.append((event, json.loads(data)))
    return events


def _done(response) -> dict:
    return next(data for event, data in _events(response) if event == "done")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    store = VectorStore(persist_dir=str(tmp_path / "qdrant"))
    llm = _RecordingLLM()
    app.dependency_overrides[get_llm_provider] = lambda: llm
    app.dependency_overrides[get_vector_store] = lambda: store
    yield llm, store, tmp_path / "uploads"
    app.dependency_overrides.pop(get_llm_provider, None)
    app.dependency_overrides.pop(get_vector_store, None)


def _stored_files(upload_dir: Path) -> list[Path]:
    return [p for p in upload_dir.rglob("*") if p.is_file()] if upload_dir.exists() else []


# --- Attaching images ---------------------------------------------------------------


def test_image_attachment_reaches_the_model_and_is_stored(client, db_engine, env):
    llm, store, upload_dir = env
    response = client.post(
        "/chat",
        data={"message": "What does this error mean?"},
        files=[("files", ("error.png", _png(), "image/png"))],
    )

    assert response.status_code == 200
    parts = _image_parts(llm.calls[0])
    assert len(parts) == 1 and parts[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert 'filename="error.png"' in message_text(llm.calls[0])

    conversation_id = _done(response)["conversation_id"]
    messages = client.get(f"/conversations/{conversation_id}/messages").json()
    assert messages[0]["attachments"] == [
        {"filename": "error.png", "mime": "image/png", "size": len(_png()), "truncated": False}
    ]
    assert "uri" not in json.dumps(messages)  # storage locations never reach the client
    assert len(_stored_files(upload_dir)) == 1


def test_attachments_are_never_indexed(client, env):
    llm, store, _ = env
    client.post("/chat", data={"message": "hi"}, files=[("files", ("notes.txt", b"secret notes", "text/plain"))])

    assert store.keyword_query("secret notes", top_k=5) == []
    assert not any("secret notes" in t for t in llm.embedded)


@pytest.mark.parametrize(
    "files, status",
    [
        ([("files", ("virus.exe", b"MZ", "application/octet-stream"))], 400),
        ([("files", (f"f{i}.txt", b"x", "text/plain")) for i in range(6)], 400),
        ([("files", ("fake.png", b"not an image", "image/png"))], 400),
    ],
)
def test_invalid_attachments_are_rejected_before_anything_is_stored(client, db_engine, env, files, status):
    _, _, upload_dir = env
    response = client.post("/chat", data={"message": "hi"}, files=files)

    assert response.status_code == status
    assert _stored_files(upload_dir) == []
    with Session(db_engine) as session:
        assert session.exec(select(Message)).first() is None


def test_oversized_attachment_is_rejected(client, env, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_size_mb", 0)
    response = client.post("/chat", data={"message": "hi"}, files=[("files", ("a.txt", b"x", "text/plain"))])
    assert response.status_code == 413


def test_message_without_text_or_files_is_rejected(client, env):
    assert client.post("/chat", data={"message": "   "}).status_code == 422


# --- Attaching documents --------------------------------------------------------------


def test_document_attachment_is_extracted_with_a_status_event_and_cached(client, db_engine, env):
    llm, _, upload_dir = env
    response = client.post(
        "/chat",
        data={"message": "Summarize this"},
        files=[("files", ("notes.md", b"# Notes\n\nThe launch is on Friday.", "text/markdown"))],
    )

    events = _events(response)
    first_token = next(i for i, (event, _) in enumerate(events) if event == "token")
    status = next(i for i, (event, data) in enumerate(events) if event == "status" and "notes.md" in data["text"])
    assert status < first_token

    prompt = message_text(llm.calls[0])
    assert '<attachment filename="notes.md">' in prompt and "The launch is on Friday." in prompt
    assert "not instructions" in prompt

    with Session(db_engine) as session:
        attachment = session.exec(select(Message).where(Message.role == "user")).one().attachments[0]
    assert storage.read(attachment["text_uri"]).decode().endswith("The launch is on Friday.")


def test_long_document_is_truncated_and_flagged(client, env, monkeypatch):
    llm, _, _ = env
    monkeypatch.setattr("app.services.attachments.MAX_TEXT_CHARS", 10)
    response = client.post(
        "/chat", data={"message": "Read this"}, files=[("files", ("long.txt", b"x" * 100, "text/plain"))]
    )

    assert "[Truncated" in message_text(llm.calls[0])
    messages = client.get(f"/conversations/{_done(response)['conversation_id']}/messages").json()
    assert messages[0]["attachments"][0]["truncated"] is True


def test_unreadable_document_gives_an_error_event(client, env):
    response = client.post(
        "/chat", data={"message": "Read this"}, files=[("files", ("broken.pdf", b"not a pdf", "application/pdf"))]
    )

    assert response.status_code == 200
    assert _events(response)[-1][0] == "error"


# --- Follow-ups and attachment-only messages ----------------------------------------------


def test_follow_ups_resend_attachments_inside_the_history_window(client, env, monkeypatch):
    llm, _, _ = env
    first = client.post("/chat", data={"message": "Look"}, files=[("files", ("a.png", _png(), "image/png"))])
    conversation_id = _done(first)["conversation_id"]

    client.post("/chat", data={"message": "And now?", "conversation_id": conversation_id})
    assert len(_image_parts(llm.calls[1])) == 1

    monkeypatch.setattr("app.routers.chat._HISTORY_LIMIT", 2)  # the image's message falls out
    client.post("/chat", data={"message": "Still there?", "conversation_id": conversation_id})
    assert _image_parts(llm.calls[2]) == []


def test_attachment_only_message_skips_retrieval_and_takes_its_title_from_the_file(client, env):
    llm, _, _ = env
    response = client.post("/chat", data={"message": ""}, files=[("files", ("screenshot.png", _png(), "image/png"))])

    assert llm.embedded == []  # nothing to search the knowledge base with
    assert len(_image_parts(llm.calls[0])) == 1
    conversation = next(c for c in client.get("/conversations").json() if c["id"] == _done(response)["conversation_id"])
    assert conversation["title"] == "screenshot.png"


# --- Serving and deleting attachments ------------------------------------------------------


def test_attachment_is_served_only_to_its_owner(client, db_engine, env):
    response = client.post("/chat", data={"message": "hi"}, files=[("files", ("a.png", _png(), "image/png"))])
    conversation_id = _done(response)["conversation_id"]
    message_id = client.get(f"/conversations/{conversation_id}/messages").json()[0]["id"]
    url = f"/conversations/{conversation_id}/messages/{message_id}/attachments/0"

    own = client.get(url)
    assert own.status_code == 200 and own.content == _png() and own.headers["content-type"] == "image/png"
    assert client.get(url.replace("/0", "/1")).status_code == 404

    same_company = _registered_client(db_engine, "colleague@example.com")
    other_company = _registered_client(db_engine, "outsider@example.com", company_name="Other Co")
    assert same_company.get(url).status_code == 404
    assert other_company.get(url).status_code == 404


def test_deleting_a_conversation_deletes_its_attachment_files(client, env):
    _, _, upload_dir = env
    response = client.post(
        "/chat",
        data={"message": "hi"},
        files=[("files", ("a.png", _png(), "image/png")), ("files", ("b.md", b"# B\n\nbody", "text/markdown"))],
    )
    assert len(_stored_files(upload_dir)) == 3  # two files and b.md's extracted text

    assert client.delete(f"/conversations/{_done(response)['conversation_id']}").status_code == 204
    assert _stored_files(upload_dir) == []


def test_conversation_delete_succeeds_when_storage_delete_fails(client, env, monkeypatch, caplog):
    response = client.post("/chat", data={"message": "hi"}, files=[("files", ("a.png", _png(), "image/png"))])

    def broken_delete(location):
        raise OSError("bucket unavailable")

    monkeypatch.setattr(storage, "delete", broken_delete)
    assert client.delete(f"/conversations/{_done(response)['conversation_id']}").status_code == 204
    assert any(r.message == "storage_delete_failed" for r in caplog.records)


# --- Document images in answers ------------------------------------------------------------


def _document_with_image(db_engine, user_email: str, *, department: str | None = None) -> Document:
    with Session(db_engine, expire_on_commit=False) as session:
        user = session.exec(select(User).where(User.email == user_email)).one()
        department_id = None
        if department:
            dept = Department(name=department, company_id=user.company_id)
            session.add(dept)
            session.commit()
            department_id = dept.id
        document_id = uuid.uuid4()
        document = Document(
            id=document_id,
            company_id=user.company_id,
            uploaded_by=user.id,
            filename="deploy-guide.pdf",
            content_type="application/pdf",
            file_path=storage.save(f"{document_id}.pdf", b"%PDF"),
            file_hash=uuid.uuid4().hex,
            status="ready",
            visibility="department" if department else "company",
            department_id=department_id,
            images=[{"uri": storage.save(f"document-images/{document_id}/0.png", _png()), "page": 2,
                     "caption": "Deployment flow: build, test, deploy"}],
        )
        session.add(document)
        session.commit()
        return document


def _index(store: VectorStore, document: Document) -> None:
    store.upsert_chunks(
        document_id=str(document.id),
        user_id=str(document.uploaded_by),
        company_id=str(document.company_id),
        filename=document.filename,
        chunks=[Chunk(text="Deployment goes build, then test, then deploy.", index=0, h1=None, h2=None,
                      images=[{"index": 0, "caption": "Deployment flow: build, test, deploy"}])],
        embeddings=[[1.0, 0.0]],
    )


def test_answers_show_retrieved_document_images_and_drop_invented_ones(client, db_engine, env):
    llm, store, _ = env
    document = _document_with_image(db_engine, "test-user@example.com")
    _index(store, document)
    # The valid reference arrives split across tokens; img:7 was never offered.
    llm.answer = ["Here is the flow:\n\n![Deployment", " flow](im", "g:1)\n\n", "Not this ![x](img:7) one."]

    response = client.post("/chat", data={"message": "How does deployment work?"})

    prompt = message_text(llm.calls[0])
    assert "img:1 - from deploy-guide.pdf: Deployment flow: build, test, deploy" in prompt
    path = f"/documents/{document.id}/images/0"
    expected = f"Here is the flow:\n\n![Deployment flow]({path})\n\nNot this  one."
    streamed = "".join(data["text"] for event, data in _events(response) if event == "token")
    assert streamed == expected
    messages = client.get(f"/conversations/{_done(response)['conversation_id']}/messages").json()
    assert messages[1]["content"] == expected

    image = client.get(path)
    assert image.status_code == 200 and image.content == _png()


def test_document_images_follow_department_visibility(client, db_engine, env):
    document = _document_with_image(db_engine, "test-user@example.com", department="Engineering")
    path = f"/documents/{document.id}/images/0"

    admin = _registered_client(db_engine, "admin-user@example.com", role="admin")
    assert admin.get(path).status_code == 200
    assert client.get(path).status_code == 404  # member outside Engineering
    assert client.get(f"/documents/{document.id}/images/5").status_code == 404


def test_deleting_a_document_deletes_its_images(db_engine, env):
    _, _, upload_dir = env
    admin = _registered_client(db_engine, "admin-user@example.com", role="admin")
    document = _document_with_image(db_engine, "admin-user@example.com")

    assert admin.delete(f"/documents/{document.id}").status_code == 204
    assert _stored_files(upload_dir) == []
