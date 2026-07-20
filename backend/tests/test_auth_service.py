import uuid

import pytest
from jose import jwt

from app.config import settings
from app.services.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_does_not_return_the_raw_password():
    hashed = hash_password("correct horse battery staple")

    assert hashed != "correct horse battery staple"
    assert hashed.startswith("$2b$")


def test_verify_password_accepts_the_correct_password():
    hashed = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_the_wrong_password():
    hashed = hash_password("correct horse battery staple")

    assert verify_password("wrong password", hashed) is False


def test_create_access_token_encodes_the_user_id_as_the_subject():
    user_id = uuid.uuid4()

    token = create_access_token(user_id)
    claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

    assert claims["sub"] == str(user_id)


def test_decode_access_token_returns_the_user_id():
    user_id = uuid.uuid4()
    token = create_access_token(user_id)

    assert decode_access_token(token) == user_id


def test_decode_access_token_rejects_a_garbage_token():
    with pytest.raises(Exception):
        decode_access_token("not-a-real-token")


def test_decode_access_token_rejects_a_token_signed_with_a_different_secret():
    other_token = jwt.encode({"sub": str(uuid.uuid4())}, "a-different-secret", algorithm=settings.jwt_algorithm)

    with pytest.raises(Exception):
        decode_access_token(other_token)
