import uuid

from sqlmodel import Session

from app.models.user import User

# No auth until Task 16 - every conversation/message is owned by this fixed
# user, and str(SEED_USER_ID) is what Chroma's user_id metadata filter uses.
SEED_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
SEED_USER_EMAIL = "seed-user@knowledgehub.local"


def ensure_seed_user(session: Session) -> None:
    if session.get(User, SEED_USER_ID) is not None:
        return
    session.add(
        User(
            id=SEED_USER_ID,
            email=SEED_USER_EMAIL,
            password_hash="unusable-until-task-16-auth",
            display_name="Seed User",
        )
    )
    session.commit()
