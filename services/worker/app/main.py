"""Idle infrastructure worker. No jobs or workflow execution in Phase 1."""
import asyncio
import logging
import os
from pathlib import Path
import signal
import time

from support_common.database import check_database
from support_common.logging import configure_logging

HEARTBEAT = Path("/tmp/worker-heartbeat")
logger = logging.getLogger(__name__)


async def run(stop: asyncio.Event) -> None:
    interval = float(os.getenv("WORKER_CHECK_INTERVAL", "5"))
    connected = False
    HEARTBEAT.unlink(missing_ok=True)
    logger.info("Worker started; waiting for PostgreSQL")
    try:
        while not stop.is_set():
            try:
                await check_database()
                if not connected:
                    logger.info("PostgreSQL connected; idle and waiting for future work")
                connected = True
                HEARTBEAT.write_text(str(time.time()))
            except Exception as exc:
                connected = False
                HEARTBEAT.unlink(missing_ok=True)
                logger.warning("PostgreSQL unavailable (%s); retrying", type(exc).__name__)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except TimeoutError:
                pass
    finally:
        HEARTBEAT.unlink(missing_ok=True)
        logger.info("Worker stopped gracefully")


async def main() -> None:
    configure_logging()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await run(stop)


if __name__ == "__main__":
    asyncio.run(main())
