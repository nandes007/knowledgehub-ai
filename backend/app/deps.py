from typing import Annotated

from fastapi import Depends, Header, HTTPException
from jose import JWTError
from sqlmodel import Session

from app.db import get_session
from app.models.user import User
from app.services.auth import decode_access_token

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(session: SessionDep, authorization: str | None = Header(default=None)) -> User:
    unauthorized = HTTPException(
        status_code=401,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if authorization is None or not authorization.startswith("Bearer "):
        raise unauthorized

    try:
        user_id = decode_access_token(authorization.removeprefix("Bearer "))
    except JWTError as exc:
        raise unauthorized from exc

    user = session.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
