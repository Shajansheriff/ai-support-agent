"""Read environment configuration once when constructing the application."""
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen3:4b"
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://localhost:3001")
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.getenv("DATABASE_URL", "postgresql://support:support_dev_password@postgres:5432/support"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:4b"),
            cors_origins=tuple(origin.strip() for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:3000,http://localhost:3001"
            ).split(",") if origin.strip()),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
