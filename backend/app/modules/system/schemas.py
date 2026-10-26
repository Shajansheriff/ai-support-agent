from typing import Literal

from pydantic import BaseModel

from app.integrations.ollama import OllamaHealth


class HealthResponse(BaseModel):
    service: Literal["backend"] = "backend"
    status: Literal["healthy"] = "healthy"


class ReadyResponse(BaseModel):
    service: Literal["backend"] = "backend"
    status: Literal["ready", "not_ready"]
    database: Literal["connected", "unavailable"]


class SystemStatus(BaseModel):
    status: Literal["healthy", "degraded"]
    database: Literal["connected", "unavailable"]
    ollama: OllamaHealth
