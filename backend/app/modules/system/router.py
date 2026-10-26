from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.core.config import Settings
from app.integrations.ollama import OllamaHealth, ollama_health
from . import service
from .schemas import HealthResponse, ReadyResponse, SystemStatus

router = APIRouter(tags=["system"])


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@router.get("/ready", response_model=ReadyResponse, responses={503: {"model": ReadyResponse}})
async def ready(settings: AppSettings, response: Response) -> ReadyResponse:
    result = await service.readiness(settings)
    if result.status != "ready":
        response.status_code = 503
    return result


@router.get("/integrations/ollama/health", response_model=OllamaHealth)
async def ollama_status(settings: AppSettings) -> OllamaHealth:
    return await ollama_health(settings)


@router.get("/api/system/status", response_model=SystemStatus)
async def system_status(settings: AppSettings) -> SystemStatus:
    return await service.system_status(settings)
