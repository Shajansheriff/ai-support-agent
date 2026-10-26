import asyncio
import os

import httpx
from pydantic import BaseModel

SERVICE_URLS = {
    name: os.getenv(f"{name.upper()}_BASE_URL", f"http://{name}:8000")
    for name in ("agent", "orders", "refunds", "approvals")
}


class ServiceStatus(BaseModel):
    reachable: bool
    error: str | None = None


class SystemStatus(BaseModel):
    status: str
    services: dict[str, ServiceStatus]


async def probe(client: httpx.AsyncClient, name: str, url: str) -> ServiceStatus:
    try:
        response = await client.get(f"{url.rstrip('/')}/health")
        response.raise_for_status()
        body = response.json()
        if body.get("service") != name or body.get("status") != "healthy":
            raise ValueError("Unexpected health response")
        return ServiceStatus(reachable=True)
    except (httpx.HTTPError, ValueError, AttributeError) as exc:
        return ServiceStatus(reachable=False, error=f"Health check failed ({type(exc).__name__})")


async def system_status() -> SystemStatus:
    async with httpx.AsyncClient(timeout=3) as client:
        results = await asyncio.gather(
            *(probe(client, name, url) for name, url in SERVICE_URLS.items())
        )
    services = dict(zip(SERVICE_URLS, results))
    return SystemStatus(
        status="healthy" if all(s.reachable for s in results) else "degraded",
        services=services,
    )
