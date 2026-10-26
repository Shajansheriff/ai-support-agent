import asyncio
import importlib
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from agent_app import integrations
from agent_app import main as agent
from gateway_app import connectivity
from gateway_app import main as gateway
from worker_app import main as worker
from support_common import database


@pytest.mark.parametrize("name", ["gateway", "agent", "orders", "refunds", "approvals"])
def test_health(name):
    app = importlib.import_module(f"{name}_app.main").app
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"service": name, "status": "healthy"}


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://localhost:3001"])
def test_gateway_cors(origin):
    with TestClient(gateway.app) as client:
        response = client.get("/health", headers={"Origin": origin})
    assert response.headers["access-control-allow-origin"] == origin


def test_unlisted_origin_not_allowed():
    with TestClient(gateway.app) as client:
        response = client.get("/health", headers={"Origin": "https://example.com"})
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("offline", [False, True])
def test_agent_readiness(monkeypatch, offline):
    probe = AsyncMock(side_effect=OSError("secret-password") if offline else None)
    monkeypatch.setattr(agent, "check_database", probe)
    with TestClient(agent.app) as client:
        response = client.get("/ready")
        assert client.get("/health").status_code == 200
    assert response.status_code == (503 if offline else 200)
    assert response.json()["database"] == ("unavailable" if offline else "connected")
    assert "secret-password" not in response.text


def mock_http(monkeypatch, module, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: original(
        transport=httpx.MockTransport(handler), **kwargs
    ))


@pytest.mark.parametrize("failure", [None, "offline", "timeout", "http", "invalid"])
def test_gateway_aggregates_partial_failures(monkeypatch, failure):
    def handler(request):
        name = request.url.host
        if name == "orders" and failure:
            if failure == "offline":
                raise httpx.ConnectError("unavailable", request=request)
            if failure == "timeout":
                raise httpx.ReadTimeout("timed out", request=request)
            if failure == "http":
                return httpx.Response(503)
            return httpx.Response(200, json={"unexpected": True})
        return httpx.Response(200, json={"service": name, "status": "healthy"})
    mock_http(monkeypatch, connectivity, handler)
    with TestClient(gateway.app) as client:
        response = client.get("/api/system/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == ("degraded" if failure else "healthy")
    assert body["services"]["orders"]["reachable"] is (failure is None)
    assert all(body["services"][name]["reachable"] for name in ("agent", "refunds", "approvals"))


@pytest.mark.parametrize("case", ["installed", "missing", "offline", "timeout", "invalid", "http"])
def test_ollama_optional(monkeypatch, case):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:4b")
    def handler(request):
        assert request.url.path == "/api/tags"
        if case == "offline":
            raise httpx.ConnectError("offline", request=request)
        if case == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        if case == "invalid":
            return httpx.Response(200, json={"models": [None]})
        if case == "http":
            return httpx.Response(500)
        return httpx.Response(200, json={"models": [{"name": "qwen3:4b"}] if case == "installed" else []})
    mock_http(monkeypatch, integrations, handler)
    with TestClient(agent.app) as client:
        body = client.get("/integrations/ollama/health").json()
        assert client.get("/health").status_code == 200
    assert body["reachable"] is (case in ("installed", "missing"))
    assert body["model_installed"] is (case == "installed")
    assert body["configured_model"] == "qwen3:4b"
    if not body["reachable"]:
        assert body["error"]


async def test_database_closes_connection_on_query_failure(monkeypatch):
    connection = AsyncMock()
    connection.fetchval.side_effect = OSError("query failed")
    connect = AsyncMock(return_value=connection)
    monkeypatch.setattr(database.asyncpg, "connect", connect)
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")
    with pytest.raises(OSError):
        await database.check_database()
    connection.fetchval.assert_awaited_once_with("SELECT 1")
    connection.close.assert_awaited_once()


async def test_worker_retries_recovers_and_stops(monkeypatch, tmp_path):
    heartbeat = tmp_path / "heartbeat"
    monkeypatch.setattr(worker, "HEARTBEAT", heartbeat)
    monkeypatch.setenv("WORKER_CHECK_INTERVAL", "0.01")
    stop = asyncio.Event()
    attempts = 0
    async def probe():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("database restarting")
        if attempts == 3:
            assert heartbeat.exists()
            stop.set()
    monkeypatch.setattr(worker, "check_database", probe)
    await asyncio.wait_for(worker.run(stop), timeout=2)
    assert attempts == 3
    assert not heartbeat.exists()
