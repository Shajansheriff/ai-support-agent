from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.infrastructure import database
from app.integrations import ollama
from app.main import create_app
from app.modules.system import service


@pytest.fixture
def settings():
    return Settings(database_url="postgresql://test-only", ollama_model="qwen3:4b")


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


def test_health_independent_of_dependencies(monkeypatch, client):
    probe = AsyncMock(side_effect=AssertionError("Liveness must not query dependencies"))
    monkeypatch.setattr(service, "check_database", probe)
    monkeypatch.setattr(service, "ollama_health", probe)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"service": "backend", "status": "healthy"}
    probe.assert_not_awaited()


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://localhost:3001"])
def test_cors(client, origin):
    response = client.get("/health", headers={"Origin": origin})
    assert response.headers["access-control-allow-origin"] == origin


def test_unlisted_origin_not_allowed(client):
    response = client.get("/health", headers={"Origin": "https://example.com"})
    assert "access-control-allow-origin" not in response.headers


def test_configured_cors_origin(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", " http://localhost:13001, ")
    settings = Settings.from_env()
    assert settings.cors_origins == ("http://localhost:13001",)
    with TestClient(create_app(settings)) as client:
        response = client.get("/health", headers={"Origin": "http://localhost:13001"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:13001"


def test_readiness_failure_and_recovery(monkeypatch, client, settings, caplog):
    probe = AsyncMock(side_effect=[OSError("secret-password"), None])
    monkeypatch.setattr(service, "check_database", probe)
    failed = client.get("/ready")
    assert failed.status_code == 503
    assert failed.json() == {"service": "backend", "status": "not_ready", "database": "unavailable"}
    assert "secret-password" not in failed.text + caplog.text
    assert client.get("/health").status_code == 200
    recovered = client.get("/ready")
    assert recovered.status_code == 200
    assert recovered.json()["database"] == "connected"
    probe.assert_awaited_with(settings.database_url)


def mock_http(monkeypatch, handler):
    original = httpx.AsyncClient
    def factory(**kwargs):
        assert kwargs["timeout"] == 3
        return original(transport=httpx.MockTransport(handler), **kwargs)
    monkeypatch.setattr(ollama.httpx, "AsyncClient", factory)


@pytest.mark.parametrize("db_online", [True, False])
@pytest.mark.parametrize("ollama_online", [True, False])
def test_system_diagnostics(monkeypatch, client, db_online, ollama_online):
    monkeypatch.setattr(service, "check_database", AsyncMock(
        side_effect=None if db_online else OSError("unavailable")
    ))
    def handler(request):
        if not ollama_online:
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(200, json={"models": []})
    mock_http(monkeypatch, handler)
    response = client.get("/api/system/status")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "database", "ollama"}
    assert body["status"] == ("healthy" if db_online else "degraded")
    assert body["database"] == ("connected" if db_online else "unavailable")
    assert body["ollama"]["reachable"] == ollama_online


@pytest.mark.parametrize("case", ["installed", "missing", "offline", "timeout", "invalid", "invalid_json", "http"])
def test_ollama_optional(monkeypatch, client, case):
    monkeypatch.setattr(service, "check_database", AsyncMock())
    def handler(request):
        assert request.url.path == "/api/tags"
        if case == "offline":
            raise httpx.ConnectError("offline", request=request)
        if case == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        if case == "invalid":
            return httpx.Response(200, json={"models": [None]})
        if case == "invalid_json":
            return httpx.Response(200, text="not JSON")
        if case == "http":
            return httpx.Response(500)
        return httpx.Response(200, json={"models": [{"name": "qwen3:4b"}] if case == "installed" else []})
    mock_http(monkeypatch, handler)
    response = client.get("/integrations/ollama/health")
    assert response.status_code == 200
    body = response.json()
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    assert body["reachable"] is (case in ("installed", "missing"))
    assert body["model_installed"] is (case == "installed")
    assert body["configured_model"] == "qwen3:4b"
    assert body["available_models"] == (["qwen3:4b"] if case == "installed" else [])
    assert bool(body["error"]) is (case not in ("installed", "missing"))


@pytest.mark.parametrize("query_fails", [True, False])
async def test_database_closes_connection(monkeypatch, query_fails):
    connection = AsyncMock()
    connection.fetchval.return_value = 1
    if query_fails:
        connection.fetchval.side_effect = OSError("query failed")
    connect = AsyncMock(return_value=connection)
    monkeypatch.setattr(database.asyncpg, "connect", connect)
    if query_fails:
        with pytest.raises(OSError):
            await database.check_database("postgresql://example")
    else:
        await database.check_database("postgresql://example")
    connect.assert_awaited_once_with("postgresql://example", timeout=3, command_timeout=3)
    connection.fetchval.assert_awaited_once_with("SELECT 1")
    connection.close.assert_awaited_once()
