import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from httpx import AsyncClient


class TestCreatePlatformAccount:
    """POST /api/platforms/accounts"""

    async def test_create_success(self, authenticated_client: AsyncClient):
        response = await authenticated_client.post(
            "/api/platforms/accounts",
            json={
                "platform_type": "sleeper",
                "platform_username": "sleeper_user",
                "platform_user_id": "123456789",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["platform_type"] == "sleeper"
        assert data["platform_username"] == "sleeper_user"
        assert data["platform_user_id"] == "123456789"
        assert "id" in data
        assert "created_at" in data

    async def test_create_duplicate_platform_type(self, authenticated_client: AsyncClient):
        # Create first account
        await authenticated_client.post(
            "/api/platforms/accounts",
            json={
                "platform_type": "espn",
                "platform_username": "espn_user",
                "platform_user_id": "espn123",
            },
        )

        # Try to create another with the same platform type
        response = await authenticated_client.post(
            "/api/platforms/accounts",
            json={
                "platform_type": "espn",
                "platform_username": "espn_user_2",
                "platform_user_id": "espn456",
            },
        )
        assert response.status_code == 409

    async def test_create_unauthenticated(self, client: AsyncClient):
        response = await client.post(
            "/api/platforms/accounts",
            json={
                "platform_type": "sleeper",
                "platform_username": "sleeper_user",
            },
        )
        assert response.status_code == 401


class TestListPlatformAccounts:
    """GET /api/platforms/accounts"""

    async def test_list_success(self, authenticated_client: AsyncClient):
        # Create an account first
        await authenticated_client.post(
            "/api/platforms/accounts",
            json={
                "platform_type": "sleeper",
                "platform_username": "sleeper_user",
                "platform_user_id": "123",
            },
        )

        response = await authenticated_client.get("/api/platforms/accounts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["platform_type"] == "sleeper"

    async def test_list_empty(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/platforms/accounts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_list_unauthenticated(self, client: AsyncClient):
        response = await client.get("/api/platforms/accounts")
        assert response.status_code == 401


class TestDeletePlatformAccount:
    """DELETE /api/platforms/accounts/{id}"""

    async def test_delete_success(self, authenticated_client: AsyncClient):
        # Create an account first
        create_resp = await authenticated_client.post(
            "/api/platforms/accounts",
            json={
                "platform_type": "mfl",
                "platform_username": "mfl_user",
                "platform_user_id": "mfl123",
            },
        )
        account_id = create_resp.json()["id"]

        response = await authenticated_client.delete(f"/api/platforms/accounts/{account_id}")
        assert response.status_code == 204

    async def test_delete_not_found(self, authenticated_client: AsyncClient):
        fake_id = uuid.uuid4()
        response = await authenticated_client.delete(f"/api/platforms/accounts/{fake_id}")
        assert response.status_code == 404

    async def test_delete_unauthenticated(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        response = await client.delete(f"/api/platforms/accounts/{fake_id}")
        assert response.status_code == 401


def _mock_mfl_response(status_code: int, text: str) -> AsyncMock:
    """Build a mock httpx.AsyncClient that returns the given response."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = status_code
    mock_resp.text = text

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


_MFL_SUCCESS_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<status cookie_name="MFL_USER_ID" cookie_value="abc123"/>'
)

_MFL_INVALID_CREDS_XML = (
    '<?xml version="1.0" encoding="UTF-8"?><status error="Invalid username or password"/>'
)


class TestMFLLogin:
    """POST /api/platforms/accounts/mfl/login"""

    async def test_mfl_login_success(self, authenticated_client: AsyncClient):
        mock_client = _mock_mfl_response(200, _MFL_SUCCESS_XML)

        with patch("app.api.platforms.httpx.AsyncClient", return_value=mock_client):
            response = await authenticated_client.post(
                "/api/platforms/accounts/mfl/login",
                json={"username": "mfl_user", "password": "secret"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["platform_type"] == "mfl"
        assert data["platform_username"] == "mfl_user"
        assert "id" in data

    async def test_mfl_login_invalid_credentials(self, authenticated_client: AsyncClient):
        mock_client = _mock_mfl_response(200, _MFL_INVALID_CREDS_XML)

        with patch("app.api.platforms.httpx.AsyncClient", return_value=mock_client):
            response = await authenticated_client.post(
                "/api/platforms/accounts/mfl/login",
                json={"username": "mfl_user", "password": "wrong"},
            )

        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["detail"]

    async def test_mfl_login_duplicate_account(self, authenticated_client: AsyncClient):
        mock_client = _mock_mfl_response(200, _MFL_SUCCESS_XML)

        with patch("app.api.platforms.httpx.AsyncClient", return_value=mock_client):
            # First login succeeds
            first = await authenticated_client.post(
                "/api/platforms/accounts/mfl/login",
                json={"username": "mfl_user", "password": "secret"},
            )
            assert first.status_code == 201

            # Second login for same user should 409
            response = await authenticated_client.post(
                "/api/platforms/accounts/mfl/login",
                json={"username": "mfl_user", "password": "secret"},
            )

        assert response.status_code == 409

    async def test_mfl_login_api_failure(self, authenticated_client: AsyncClient):
        mock_client = _mock_mfl_response(500, "Internal Server Error")

        with patch("app.api.platforms.httpx.AsyncClient", return_value=mock_client):
            response = await authenticated_client.post(
                "/api/platforms/accounts/mfl/login",
                json={"username": "mfl_user", "password": "secret"},
            )

        assert response.status_code == 502
        assert "MFL API request failed" in response.json()["detail"]

    async def test_mfl_login_unauthenticated(self, client: AsyncClient):
        response = await client.post(
            "/api/platforms/accounts/mfl/login",
            json={"username": "mfl_user", "password": "secret"},
        )
        assert response.status_code == 401
