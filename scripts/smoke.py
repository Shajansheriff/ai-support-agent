#!/usr/bin/env python3
"""Live stack checks. Standard library only; run from any directory."""
import argparse
import json
import time
from urllib.request import urlopen


def get(port, path="/", as_json=True):
    with urlopen(f"http://localhost:{port}{path}", timeout=6) as response:
        body = response.read().decode()
        return json.loads(body) if as_json else body


def check(ollama_mode, operator_port):
    assert get(8000, "/health") == {"service": "backend", "status": "healthy"}
    status = get(8000, "/api/system/status")
    assert status["status"] == "healthy", status
    assert status["database"] == "connected", status
    assert get(8000, "/ready")["database"] == "connected"
    for port, title in [(3000, "AI Store Support"), (operator_port, "Support Operator Console")]:
        assert title in get(port, as_json=False), title
    ollama = get(8000, "/integrations/ollama/health")
    assert set(status["ollama"]) == set(ollama)
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
            print("PASS: backend API, database readiness, system diagnostics, both frontends")
            print("PASS: Ollama report:", json.dumps(ollama))
            return
        except Exception as exc:
            if time.monotonic() >= deadline:
                raise SystemExit(f"FAIL: {type(exc).__name__}: {exc}") from exc
            time.sleep(2)


if __name__ == "__main__":
    main()
