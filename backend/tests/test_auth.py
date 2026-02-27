from httpx import AsyncClient


class TestRegister:
    """POST /api/auth/register"""

    async def test_register_success(self, client: AsyncClient):
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
                "display_name": "New User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["display_name"] == "New User"
        assert "id" in data
        assert "created_at" in data
        assert "password" not in data
        assert "hashed_password" not in data

    async def test_register_duplicate_email(self, client: AsyncClient):
        # Register a user first via the API
        await client.post(
            "/api/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "password123456",
                "display_name": "First User",
            },
        )

        # Try to register with the same email
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "password123456",
                "display_name": "Second User",
            },
        )
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"].lower()

    async def test_register_invalid_email(self, client: AsyncClient):
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "not-an-email",
                "password": "securepassword123",
            },
        )
        assert response.status_code == 422

    async def test_register_short_password(self, client: AsyncClient):
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "valid@example.com",
                "password": "short",
            },
        )
        assert response.status_code == 422


class TestLogin:
    """POST /api/auth/login"""

    async def test_login_success(self, client: AsyncClient):
        # Register a user first
        await client.post(
            "/api/auth/register",
            json={
                "email": "loginuser@example.com",
                "password": "correctpassword",
                "display_name": "Login User",
            },
        )

        response = await client.post(
            "/api/auth/login",
            json={
                "email": "loginuser@example.com",
                "password": "correctpassword",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient):
        # Register a user first
        await client.post(
            "/api/auth/register",
            json={
                "email": "wrongpwd@example.com",
                "password": "correctpassword",
                "display_name": "Wrong Pwd User",
            },
        )

        response = await client.post(
            "/api/auth/login",
            json={
                "email": "wrongpwd@example.com",
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401

    async def test_login_nonexistent_email(self, client: AsyncClient):
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "somepassword",
            },
        )
        assert response.status_code == 401


class TestGetMe:
    """GET /api/auth/me"""

    async def test_get_me_success(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "testuser@example.com"
        assert data["display_name"] == "Test User"
        assert "id" in data
        assert "created_at" in data

    async def test_get_me_no_token(self, client: AsyncClient):
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    async def test_get_me_invalid_token(self, client: AsyncClient):
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalidtoken123"},
        )
        assert response.status_code == 401
