import re
import uuid

from sqlmodel import Session, delete, select

from app.models.company import Company
from app.models.conversation import Conversation
from app.models.department import Department
from app.models.document import Document
from app.models.invite import Invite
from app.models.membership import Membership
from app.models.message import Message
from app.services import attachments
from ingestion.index import VectorStore
from ingestion.pipeline import delete_files

# Top-level paths of the web app; a company slug sits beside them in the URL.
_RESERVED_SLUGS = {"login", "register", "invite", "instance", "new", "api", "admin"}


def unique_slug(session: Session, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48].strip("-") or "company"
    taken = set(session.exec(select(Company.slug).where(Company.slug.startswith(base))))
    slug, n = base, 1
    while slug in taken or slug in _RESERVED_SLUGS:
        n += 1
        slug = f"{base}-{n}"
    return slug


def delete_conversations(session: Session, company_id: uuid.UUID, user_id: uuid.UUID | None = None) -> list[str]:
    """Delete a company's conversations (one member's, or everyone's) with their messages.
    Returns the attachment files to remove once the caller has committed."""
    statement = select(Conversation).where(Conversation.company_id == company_id)
    if user_id is not None:
        statement = statement.where(Conversation.user_id == user_id)
    files: list[str] = []
    for conversation in session.exec(statement):
        messages = list(session.exec(select(Message).where(Message.conversation_id == conversation.id)))
        files += attachments.locations([m.attachments for m in messages])
        for message in messages:
            session.delete(message)
        session.delete(conversation)
    return files


def delete_company(session: Session, company: Company, vector_store: VectorStore) -> None:
    """Remove a company and everything in it: vectors, stored files, then the rows."""
    files = delete_conversations(session, company.id)
    for document in session.exec(select(Document).where(Document.company_id == company.id)):
        vector_store.delete_by_document(str(document.id))
        files.append(document.file_path)
        files += [img["uri"] for img in document.images or []]
        session.delete(document)
    # Explicit rather than left to ON DELETE CASCADE, so it holds on any database.
    for model in (Invite, Membership, Department):
        session.exec(delete(model).where(model.company_id == company.id))
    session.delete(company)
    session.commit()
    delete_files(files)  # after the commit: a storage hiccup must not resurrect the company
