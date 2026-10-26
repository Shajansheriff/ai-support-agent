#!/usr/bin/env python3
"""Live stack checks. Standard library only; run from any directory."""
import argparse
import json
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def get(port, path="/", as_json=True):
    with urlopen(f"http://localhost:{port}{path}", timeout=6) as response:
        body = response.read().decode()
        return json.loads(body) if as_json else body


def check(ollama_mode, operator_port):
    for port, name in enumerate(("gateway", "agent", "orders", "refunds", "approvals"), 8000):
        assert get(port, "/health") == {"service": name, "status": "healthy"}, name
    status = get(8000, "/api/system/status")
    assert status["status"] == "healthy", status
    assert set(status["services"]) == {"agent", "orders", "refunds", "approvals"}
    assert all(item["reachable"] for item in status["services"].values()), status
    assert get(8001, "/ready")["database"] == "connected"
    # The heartbeat is written only after SELECT 1 in the actual worker loop.
    subprocess.run(["docker", "compose", "exec", "-T", "worker", "python", "-m", "app.healthcheck"], cwd=ROOT, check=True, capture_output=True, timeout=15)
    for port, title in [(3000, "AI Store Support"), (operator_port, "Support Operator Console")]:
        assert title in get(port, as_json=False), title
    ollama = get(8001, "/integrations/ollama/health")
    assert isinstance(ollama["reachable"], bool)
    assert isinstance(ollama["available_models"], list)
    assert ollama["model_installed"] == (ollama["configured_model"] in ollama["available_models"])
    if ollama["reachable"]:
        assert ollama["error"] is None
    else:
        assert ollama["error"] and not ollama["model_installed"]
    if ollama_mode != "any":
        assert ollama["reachable"] == (ollama_mode == "online"), ollama
    return ollama


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ollama", choices=["any", "online", "offline"], default="any")
    parser.add_argument("--wait", type=float, default=60, help="Seconds to allow startup")
    parser.add_argument("--operator-port", type=int, default=3001)
    args = parser.parse_args()
    deadline = time.monotonic() + args.wait
    while True:
        try:
            ollama = check(args.ollama, args.operator_port)
            print("PASS: five APIs, gateway dependencies, agent DB, worker heartbeat, both frontends")
            print("PASS: Ollama report:", json.dumps(ollama))
            return
        except Exception as exc:
            if time.monotonic() >= deadline:
                raise SystemExit(f"FAIL: {type(exc).__name__}: {exc}") from exc
            time.sleep(2)


if __name__ == "__main__":
    main()
