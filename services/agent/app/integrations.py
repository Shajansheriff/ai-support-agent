import os

import httpx
from pydantic import BaseModel, ValidationError


class ModelInfo(BaseModel):
    name: str


class TagsResponse(BaseModel):
    models: list[ModelInfo]


class OllamaHealth(BaseModel):
    reachable: bool
    available_models: list[str] = []
    configured_model: str
    model_installed: bool = False
    error: str | None = None


async def ollama_health() -> OllamaHealth:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    model = os.getenv("OLLAMA_MODEL", "qwen3:4b")
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
    except (httpx.HTTPError, ValueError, ValidationError) as exc:
        return OllamaHealth(
            reachable=False, configured_model=model,
            error=f"Ollama check failed ({type(exc).__name__}). Check Ollama is running and OLLAMA_BASE_URL is reachable from Docker.",
        )
