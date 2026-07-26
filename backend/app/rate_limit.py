from fastapi import Request
from jose import JWTError
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.services.auth import decode_access_token


def _rate_limit_key(request: Request) -> str:
    """Per-user limit when authenticated, per-IP otherwise (matches CurrentUserDep's auth check)."""
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer "):
        try:
            user_id = decode_access_token(authorization.removeprefix("Bearer "))
            return f"user:{user_id}"
        except JWTError:
            pass
    return get_remote_address(request)


# ponytail: in-memory limiter storage, fine for a single-process deploy.
# Swap for a Redis storage_uri if this ever runs behind multiple workers.
limiter = Limiter(key_func=_rate_limit_key)
