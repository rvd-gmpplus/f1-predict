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


class TestAuthEndpoints:
    def test_register_success(self, client):
        resp = client.post("/auth/register", json={
            "email": "new@example.com",
            "username": "newuser",
            "password": "securepass123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["access_token"]
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email(self, client, test_user):
        resp = client.post("/auth/register", json={
            "email": "test@example.com",
            "username": "other",
            "password": "password123",
        })
        assert resp.status_code == 409

    def test_login_success(self, client, test_user):
        resp = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "password123",
        })
        assert resp.status_code == 200
        assert resp.json()["access_token"]

    def test_login_wrong_password(self, client, test_user):
        resp = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_me_authenticated(self, client, test_user, auth_headers):
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"

    def test_me_unauthenticated(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code in (401, 403)
