from fastapi import FastAPI
from pydantic import BaseModel
from support_common.logging import configure_logging

configure_logging()
app = FastAPI(title="Refunds service")


class HealthResponse(BaseModel):
    service: str
    status: str


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(service="refunds", status="healthy")
