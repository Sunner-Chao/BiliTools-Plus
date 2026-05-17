"""API 端点测试"""
import pytest

@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_auth_status(client):
    resp = await client.get("/api/auth/status")
    assert resp.status_code == 200
    assert resp.json()["is_login"] == False

@pytest.mark.asyncio
async def test_qrcode_generate(client):
    resp = await client.post("/api/auth/qrcode/generate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert "qrcode_key" in data and len(data["qrcode_key"]) == 32
    assert data["expires_in"] == 180
    assert data["image"].startswith("data:image/png;base64,")

@pytest.mark.asyncio
async def test_login(client):
    resp = await client.post("/api/auth/login", params={"username": "test_user"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_login"] == True
    assert data["username"] == "test_user"
    assert "access_token" in data

@pytest.mark.asyncio
async def test_accounts_list(client):
    resp = await client.get("/api/accounts")
    assert resp.status_code == 200
    assert "accounts" in resp.json()

@pytest.mark.asyncio
async def test_tasks_list(client):
    resp = await client.get("/api/tasks")
    assert resp.status_code == 200
    assert "games" in resp.json()

@pytest.mark.asyncio
async def test_live_status(client):
    resp = await client.get("/api/live/status")
    assert resp.status_code == 200
    assert resp.json()["is_living"] == False


@pytest.mark.asyncio
async def test_games_with_tasks(client):
    """Test game config loading from JSON files."""
    resp = await client.get("/api/tasks/games")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 4
    games = {g["id"]: g for g in data["games"]}
    assert games["genshin"]["name"] == "原神"
    assert games["genshin"]["task_count"] > 0


@pytest.mark.asyncio
async def test_task_status(client):
    """Test task status endpoint."""
    resp = await client.get("/api/tasks/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "tasks" in data
    assert "count" in data
