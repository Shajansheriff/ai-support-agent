"""A recent successful DB probe proves the worker loop is alive and connected."""
import os
from pathlib import Path
import time


def main() -> None:
    try:
        last_success = float(Path("/tmp/worker-heartbeat").read_text())
        max_age = float(os.getenv("WORKER_CHECK_INTERVAL", "5")) + 15
        healthy = 0 <= time.time() - last_success < max_age
    except (OSError, ValueError):
        healthy = False
    raise SystemExit(0 if healthy else 1)


if __name__ == "__main__":
    main()
