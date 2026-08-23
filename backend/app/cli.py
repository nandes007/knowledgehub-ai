import argparse
import sys
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, select

from app.db import get_engine
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


def main(args: list[str] | None = None) -> Any:
    parser = argparse.ArgumentParser(description="KnowledgeHub AI CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_sa_parser = subparsers.add_parser("create-superadmin", help="Bootstrap a platform superadmin")
    create_sa_parser.add_argument("--email", required=True, help="Superadmin email address")
    create_sa_parser.add_argument("--password", required=True, help="Superadmin password")
    create_sa_parser.add_argument("--display-name", default="Super Admin", help="Superadmin display name")

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


if __name__ == "__main__":
    main()
