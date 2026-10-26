import httpx
from pydantic import BaseModel, Field

from app.core.config import Settings


class ModelInfo(BaseModel):
    name: str


class TagsResponse(BaseModel):
    models: list[ModelInfo]


class OllamaHealth(BaseModel):
    reachable: bool
    available_models: list[str] = Field(default_factory=list)
    configured_model: str
    model_installed: bool = False
    error: str | None = None


async def ollama_health(settings: Settings) -> OllamaHealth:
    base_url = settings.ollama_base_url
    model = settings.ollama_model
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(f"{base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            tags = TagsResponse.model_validate(response.json())
        names = [item.name for item in tags.models]
        return OllamaHealth(
            reachable=True, available_models=names, configured_model=model,
            model_installed=model in names,
        )
    except (httpx.HTTPError, ValueError) as exc:
        return OllamaHealth(
            reachable=False, configured_model=model,
            error=f"Ollama check failed ({type(exc).__name__}). Check Ollama is running and OLLAMA_BASE_URL is reachable from Docker.",
        )
