import logging
from fastapi.responses import JSONResponse
from support_common.database import check_database
from .integrations import OllamaHealth, ollama_health
from fastapi import FastAPI
from pydantic import BaseModel
from support_common.logging import configure_logging

configure_logging()
app = FastAPI(title="Agent service")


class HealthResponse(BaseModel):
    service: str
    status: str


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(service="agent", status="healthy")




class ReadyResponse(BaseModel):
    service: str = "agent"
    status: str
    database: str


@app.get("/ready", response_model=ReadyResponse, responses={503: {"model": ReadyResponse}})
async def ready():
    try:
        await check_database()
    except Exception as exc:
        # Never expose connection strings or passwords in logs or responses.
        logging.getLogger(__name__).warning("Database unavailable (%s)", type(exc).__name__)
        return JSONResponse(status_code=503, content=ReadyResponse(
            status="not_ready", database="unavailable"
        ).model_dump())
    return ReadyResponse(status="ready", database="connected")


app.get("/integrations/ollama/health", response_model=OllamaHealth)(ollama_health)
