from app.services.auth import hash_password, verify_password, create_access_token, decode_access_token


class TestPasswordHashing:
    def test_hash_password_returns_hash(self):
        hashed = hash_password("mysecret")
        assert hashed != "mysecret"
        assert len(hashed) > 20

    def test_verify_password_correct(self):
        hashed = hash_password("mysecret")
        assert verify_password("mysecret", hashed) is True

    def test_verify_password_wrong(self):
        hashed = hash_password("mysecret")
        assert verify_password("wrongpassword", hashed) is False


class TestJWT:
    def test_create_and_decode_token(self):
        token = create_access_token(user_id=42)
        payload = decode_access_token(token)
        assert payload["sub"] == 42

    def test_decode_invalid_token_returns_none(self):
        payload = decode_access_token("not.a.valid.token")
        assert payload is None
