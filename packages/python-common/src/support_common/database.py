"""Connectivity only: no shared business data or schema ownership."""
import os

import asyncpg


async def check_database() -> None:
    connection = await asyncpg.connect(
        os.environ["DATABASE_URL"], timeout=3, command_timeout=3
    )
    try:
        if await connection.fetchval("SELECT 1") != 1:
            raise RuntimeError("Unexpected database probe result")
    finally:
        await connection.close(timeout=2)
