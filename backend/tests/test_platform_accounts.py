import uuid

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

    async def test_create_duplicate_platform_type(
        self, authenticated_client: AsyncClient
    ):
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

        response = await authenticated_client.delete(
            f"/api/platforms/accounts/{account_id}"
        )
        assert response.status_code == 204

    async def test_delete_not_found(self, authenticated_client: AsyncClient):
        fake_id = uuid.uuid4()
        response = await authenticated_client.delete(
            f"/api/platforms/accounts/{fake_id}"
        )
        assert response.status_code == 404

    async def test_delete_unauthenticated(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        response = await client.delete(f"/api/platforms/accounts/{fake_id}")
        assert response.status_code == 401
