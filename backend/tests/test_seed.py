from sqlmodel import Session, select

from app.models.user import User
from app.seed import SEED_USER_ID, ensure_seed_user


def test_ensure_seed_user_creates_user_when_missing(db_engine):
    with Session(db_engine) as session:
        ensure_seed_user(session)

    with Session(db_engine) as session:
        user = session.get(User, SEED_USER_ID)
        assert user is not None
        assert user.id == SEED_USER_ID


def test_ensure_seed_user_is_idempotent(db_engine):
    with Session(db_engine) as session:
        ensure_seed_user(session)
        ensure_seed_user(session)

    with Session(db_engine) as session:
        count = len(list(session.exec(select(User).where(User.id == SEED_USER_ID))))
        assert count == 1
