import argparse
import sys
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, select

from app.db import get_engine
from app.models.document import Document
from app.models.user import User
from app.services.auth import hash_password


def create_superadmin(
    email: str,
    password: str,
    display_name: str | None = None,
    engine: Engine | None = None,
) -> User:
    target_engine = engine or get_engine()
    with Session(target_engine) as session:
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing is not None:
            raise ValueError(f"User with email '{email}' already exists.")

        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=display_name or "Super Admin",
            role="superadmin",
            approval_status="approved",
            company_id=None,
            department_id=None,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def reindex(engine: Engine | None = None, **ingest_kwargs: Any) -> tuple[int, int]:
    """Re-ingest every document from its stored file into the current vector store.
    For moving to a new store or embedding model. Safe to re-run: chunk ids are
    deterministic, so it overwrites rather than duplicates."""
    from ingestion.pipeline import ingest_document  # imports the LLM client; keep other commands light

    target_engine = engine or get_engine()
    with Session(target_engine) as session:
        document_ids = list(session.exec(select(Document.id)))

    ready = 0
    for document_id in document_ids:
        ingest_document(document_id, engine=target_engine, **ingest_kwargs)
        with Session(target_engine) as session:
            document = session.get(Document, document_id)
            error = f" - {document.error_message}" if document.status == "failed" else ""
            print(f"{document.status:<8} {document.filename}{error}")
            ready += document.status == "ready"
    return ready, len(document_ids)


def main(args: list[str] | None = None) -> Any:
    parser = argparse.ArgumentParser(description="KnowledgeHub AI CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_sa_parser = subparsers.add_parser("create-superadmin", help="Bootstrap a platform superadmin")
    create_sa_parser.add_argument("--email", required=True, help="Superadmin email address")
    create_sa_parser.add_argument("--password", required=True, help="Superadmin password")
    create_sa_parser.add_argument("--display-name", default="Super Admin", help="Superadmin display name")

    subparsers.add_parser("reindex", help="Re-ingest every document into the vector store")

    parsed = parser.parse_args(args)

    if parsed.command == "create-superadmin":
        try:
            user = create_superadmin(
                email=parsed.email,
                password=parsed.password,
                display_name=parsed.display_name,
            )
            print(f"Superadmin created successfully: {user.email} (id: {user.id})")
        except ValueError as exc:
            sys.stderr.write(f"Error: {exc}\n")
            sys.exit(1)

    elif parsed.command == "reindex":
        ready, total = reindex()
        print(f"Reindexed {ready}/{total} documents.")
        if ready < total:
            sys.exit(1)


if __name__ == "__main__":
    main()
