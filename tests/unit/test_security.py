"""Tests de seguridad: hashing y JWT."""
import pytest
from app.core.security import (
    get_password_hash, verify_password,
    create_access_token, create_refresh_token, decode_token,
)


class TestPasswordHashing:
    def test_hash_is_different_from_plain(self):
        plain = "MyPassword123"
        hashed = get_password_hash(plain)
        assert hashed != plain

    def test_verify_correct_password(self):
        plain = "MyPassword123"
        hashed = get_password_hash(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password(self):
        hashed = get_password_hash("correct")
        assert verify_password("wrong", hashed) is False


class TestJWT:
    def test_create_and_decode_access_token(self):
        user_id = "test-user-id-123"
        token = create_access_token(user_id)
        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "access"

    def test_create_and_decode_refresh_token(self):
        user_id = "test-user-id-456"
        token = create_refresh_token(user_id)
        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"

    def test_invalid_token_raises(self):
        from jose import JWTError
        with pytest.raises(JWTError):
            decode_token("invalid.token.here")
