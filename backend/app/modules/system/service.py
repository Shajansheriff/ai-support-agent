"""Infrastructure diagnostics; no self-HTTP calls or background polling."""
import asyncio
import logging

from app.core.config import Settings
from app.infrastructure.database import check_database
from app.integrations.ollama import ollama_health
from .schemas import ReadyResponse, SystemStatus

logger = logging.getLogger(__name__)


async def readiness(settings: Settings) -> ReadyResponse:
    try:
        await check_database(settings.database_url)
    except Exception as exc:
        # Exception messages can contain credentials; log only the type.
        logger.warning("Database unavailable (%s)", type(exc).__name__)
        return ReadyResponse(status="not_ready", database="unavailable")
    return ReadyResponse(status="ready", database="connected")


async def system_status(settings: Settings) -> SystemStatus:
    database, ollama = await asyncio.gather(readiness(settings), ollama_health(settings))
    return SystemStatus(
        status="healthy" if database.status == "ready" else "degraded",
        database=database.database,
        ollama=ollama,
    )
