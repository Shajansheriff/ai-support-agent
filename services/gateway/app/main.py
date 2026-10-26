import os
from fastapi.middleware.cors import CORSMiddleware
from .connectivity import SystemStatus, system_status
from fastapi import FastAPI
from pydantic import BaseModel
from support_common.logging import configure_logging

configure_logging()
app = FastAPI(title="Gateway service")


class HealthResponse(BaseModel):
    service: str
    status: str


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(service="gateway", status="healthy")



app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.get("/api/system/status", response_model=SystemStatus)(system_status)
