# AI Customer Support Agent — Phase 1

A local infrastructure playground for learning AI engineering and distributed systems.
Phase 1 provides running services, connectivity probes, and placeholder interfaces.
It does **not** implement chat, tool calls, orders, refunds, approvals, authentication,
persistence of conversations, durable execution, queues, or SSE. Those come later.

## Architecture

| Component | Responsibility now | Host URL / port |
| --- | --- | --- |
| customer-web | Placeholder customer chat and gateway indicator | http://localhost:3000 |
| operator-web | Placeholder approvals and gateway indicator | http://localhost:3001 |
| gateway | Browser API, CORS, concurrent downstream health checks | http://localhost:8000 |
| agent | Database readiness and optional Ollama connectivity | http://localhost:8001 |
| orders | Service skeleton with health endpoint | http://localhost:8002 |
| refunds | Service skeleton with health endpoint | http://localhost:8003 |
| approvals | Service skeleton with health endpoint | http://localhost:8004 |
| worker | Idle process that checks PostgreSQL and retries failures | No HTTP port |
| postgres | Persistent PostgreSQL 17 database | localhost:5432 |
| Ollama | Native macOS model server, outside Compose | http://localhost:11434 |

Compose creates one default bridge network. All five APIs listen on port **8000
inside their own container**; published host ports differ. Gateway calls
`http://orders:8000`, `http://agent:8000`, etc. Compose DNS resolves these service
names. Inside a container, `localhost` means that container, not your Mac.
The browser runs on your Mac and calls `http://localhost:8000`.

The agent and worker reach `postgres:5432` using asyncpg. The agent reaches native
Ollama through `host.docker.internal`, Docker Desktop's hostname for the Mac.
Ollama runs natively to use Apple Silicon GPU acceleration; it is never installed
in a container. See the [Ollama FAQ](https://docs.ollama.com/faq).

Each service owns its entry point, requirements, and Dockerfile. The common Python
package contains only logging and a short-lived `SELECT 1` connectivity helper.
Future services will own their schemas/tables and migrations. They should call
one another's HTTP APIs rather than access another service's data directly.
There are no business tables or migrations in Phase 1.

## Prerequisites

- Docker Desktop for Apple Silicon, started and ready (`docker info` should work).
- Git. Python 3.12+ for the optional unit tests; any modern Python 3 for smoke tests.
- Node.js 22.12+ and npm only if developing/building the UIs outside Docker.
- Optional: [Ollama for macOS](https://ollama.com/download/mac).

Docker builds use native multi-architecture Python 3.12, Node 22, and PostgreSQL
17 images; no amd64 emulation is forced. Frontend lockfiles are committed and
images install with `npm ci`.

## Start

From the repository root:

```bash
cp .env.example .env
docker compose up --build
```

Defaults also allow startup without `.env`. These are local development
credentials, not production secrets. `.env` is ignored by Git. If you customize
PostgreSQL credentials, update `DATABASE_URL` to match (URL-encode special
characters in the URL). Database initialization credentials apply only to a new
volume; editing `.env` does not change existing database passwords.

For detached mode and a bounded readiness wait:

```bash
docker compose up --build -d --wait --wait-timeout 120
docker compose ps
```

All nine containers have health checks and `unless-stopped` restart policies.
Agent and worker wait for initial PostgreSQL health. The worker keeps checking
and retrying if PostgreSQL later goes away. No service depends on Ollama starting.
API `/health` is process liveness; agent `/ready` is database readiness and returns
503 during a database outage. Docker API health checks deliberately use liveness.
The worker health check requires a recent successful database probe from its actual
main loop, not merely a separate process that can reach the database.

Open the two UIs using the URLs above. Their gateway indicators poll every ten
seconds, time out after four seconds, and recover automatically. The indicator
checks the gateway itself; `/api/system/status` checks downstream connectivity.

## Optional Ollama setup

Install and open the Ollama macOS application, or start the CLI server:

```bash
ollama serve
```

Do not start a second server if the app is already serving port 11434. In another
terminal, optionally download the configured model:

```bash
ollama pull qwen3:4b
ollama list
curl http://localhost:11434/api/tags
curl http://localhost:8001/integrations/ollama/health
```

The agent reports reachability, installed model names, configured model, whether
that model is installed, and an error when unavailable. It never generates a
response. An empty model list is valid: **no model download is required for tests**.

If the host request succeeds but the container request fails, check the server's
bind address. For the macOS app, set this and then fully quit/reopen Ollama:

```bash
launchctl setenv OLLAMA_HOST "0.0.0.0:11434"
```

For CLI-only use, stop the previous server and run:

```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

Binding all interfaces can expose this unauthenticated local API on your network;
use a trusted development network and appropriate firewall settings. The app
setting can be undone with `launchctl unsetenv OLLAMA_HOST` followed by a restart.
These settings follow the [official Ollama instructions](https://docs.ollama.com/faq#setting-environment-variables-on-mac).

## Health and smoke tests

With the stack running:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/system/status
curl http://localhost:8001/ready
curl http://localhost:8001/integrations/ollama/health
python3 scripts/smoke.py
```

The standard-library smoke script waits up to 60 seconds, checks all five APIs,
gateway-to-service communication, agent database readiness, the actual worker's
successful database heartbeat, both frontend HTML pages, and the Ollama response
contract. It exits nonzero on failure. To require live Ollama connectivity:

```bash
python3 scripts/smoke.py --ollama online
```

To verify startup with Ollama forcibly unreachable, without stopping your native
Ollama server or deleting database data:

```bash
docker compose down
docker compose -f compose.yaml -f scripts/compose.ollama-offline.yaml up --build -d --wait --wait-timeout 120
python3 scripts/smoke.py --ollama offline
# Restore the normal agent configuration afterward:
docker compose up -d --wait --wait-timeout 120
```

Unit tests use HTTP mocks and database doubles, so they need neither Docker nor a
model download. They cover healthy APIs, CORS, partial downstream failures,
timeouts, invalid Ollama responses, database readiness, connection cleanup, and
worker retry/recovery/shutdown:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Build each UI locally:

```bash
(cd apps/customer-web && npm ci && npm run build)
(cd apps/operator-web && npm ci && npm run build)
```

## Development and logs

```bash
docker compose logs -f gateway agent worker
docker compose logs --tail=100 postgres
docker compose restart worker
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1"'
```

Python APIs use Uvicorn reload and source mounts. Vite binds to `0.0.0.0`, with
only source/config files mounted. Container `node_modules` stays in the image,
so host dependencies cannot overwrite it. After dependency or package manifest
changes, update the relevant lockfile and rebuild. Worker source changes require
`docker compose restart worker`; it intentionally has no reload supervisor.
Environment changes require `docker compose up -d` to recreate affected containers.

For a single API outside Docker, install its requirements from its own directory,
then run Uvicorn (use a free port):

```bash
cd services/orders
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8002
```

When running agent/worker on the host, explicitly set `DATABASE_URL` to use
`localhost:5432`; host processes cannot resolve Compose's `postgres` name.
Similarly, host-run gateway URLs must use published localhost service ports.
Compose reads root `.env`; standalone Python processes do not load it automatically.

## Stop, preserve, or reset data

```bash
docker compose stop       # Stop processes; keep containers and data
docker compose start      # Resume existing containers
docker compose down       # Remove containers/network; preserve named volume
docker compose up -d      # Recreate containers using the same data
```

PostgreSQL stores data in the named `postgres-data` volume, mounted at
`/var/lib/postgresql/data`. Container restarts/recreation do not erase it.
To intentionally delete **all project database data** and initialize again:

```bash
docker compose down --volumes
docker compose up --build -d
```

## Troubleshooting on macOS

- **Cannot connect to Docker daemon:** launch Docker Desktop and wait for
  `docker info` to succeed. Check `docker context ls` if the wrong daemon is selected.
- **PostgreSQL port 5432 already in use:** set `POSTGRES_PORT=5433` in `.env`.
  This changes only the Mac-facing port; keep `DATABASE_URL` using `postgres:5432`
  inside Docker. Host SQL clients then use localhost:5433.
- **Operator port 3001 already in use:** set `OPERATOR_WEB_PORT=13001` and add
  `http://localhost:13001` to `CORS_ORIGINS` in `.env`. Open that port and run
  smoke tests with `--operator-port 13001`. The container still listens on 3001.
- **Port already allocated:** stop the conflicting local process or change the
  host-side published port. If gateway/UI ports change, also update
  `VITE_GATEWAY_URL` and `CORS_ORIGINS`.
- **Gateway degraded:** inspect `/api/system/status` and the relevant service logs.
  Internal URLs use service names and container port 8000, never host port 8002.
- **Ollama disconnected:** compare host `/api/tags` with the container probe:
  `docker compose exec agent python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags', timeout=3).read().decode())"`.
  Check the Ollama bind address, firewall, VPN, and Docker Desktop networking.
- **Database auth failure after editing `.env`:** the existing volume retains old
  credentials. Restore matching settings, change the password through PostgreSQL,
  or explicitly reset disposable data using the destructive command above.
- **UI indicator disconnected:** use browser developer tools to check the gateway
  URL and CORS origin. A browser cannot resolve `gateway` or `orders` as hostnames.
- **Source changes not appearing:** check Docker Desktop file-sharing access to
  this repository. Rebuild for dependency changes; restart the worker for edits.

## Repository tree

Generated dependencies, caches, build output, `.git`, and `.env` are omitted.

```text
ai-support-agent/
├── apps/
│   ├── customer-web/
│   │   ├── src/
│   │   │   ├── App.tsx
│   │   │   ├── main.tsx
│   │   │   ├── style.css
│   │   │   └── vite-env.d.ts
│   │   ├── Dockerfile
│   │   ├── index.html
│   │   ├── package-lock.json
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── vite.config.ts
│   └── operator-web/
│       ├── src/
│       │   ├── App.tsx
│       │   ├── main.tsx
│       │   ├── style.css
│       │   └── vite-env.d.ts
│       ├── Dockerfile
│       ├── index.html
│       ├── package-lock.json
│       ├── package.json
│       ├── tsconfig.json
│       └── vite.config.ts
├── infra/
│   └── postgres/
│       └── README.md
├── packages/
│   └── python-common/
│       ├── src/
│       │   └── support_common/
│       │       ├── __init__.py
│       │       ├── database.py
│       │       └── logging.py
│       └── pyproject.toml
├── scripts/
│   ├── compose.ollama-offline.yaml
│   └── smoke.py
├── services/
│   ├── agent/
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── integrations.py
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── approvals/
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── gateway/
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── connectivity.py
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── orders/
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── refunds/
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── worker/
│       ├── app/
│       │   ├── __init__.py
│       │   ├── healthcheck.py
│       │   └── main.py
│       ├── Dockerfile
│       └── requirements.txt
├── tests/
│   ├── conftest.py
│   └── test_infrastructure.py
├── .dockerignore
├── .env.example
├── .gitignore
├── README.md
├── compose.yaml
├── pytest.ini
└── requirements-dev.txt
```

## Validation performed

The implementation was validated with Python 3.12 on Apple Silicon and Docker
Desktop. All 23 Pytest cases passed, both TypeScript/Vite production builds passed,
and all nine containers reached healthy status. Browser checks confirmed both UIs
rendered and displayed a connected gateway, with no captured console errors.

Live smoke tests passed with native Ollama reachable and with Ollama deliberately
unreachable via the override file. The configured `qwen3:4b` model was absent and
correctly reported as not installed; no model was downloaded. PostgreSQL shutdown
caused agent readiness to return 503 and the worker to log retries. SIGTERM produced
the worker's graceful shutdown log. A disposable probe row survived `compose down`
and container recreation; its test table was then dropped.

On the validation machine, existing processes occupied the requested host ports.
The ignored local `.env` uses `POSTGRES_PORT=15432`, `OPERATOR_WEB_PORT=13001`, and
includes `http://localhost:13001` in CORS. Use the operator UI at
http://localhost:13001 and run `python3 scripts/smoke.py --operator-port 13001`
with that local configuration. Committed defaults remain 5432 and 3001.

The test suite reports one upstream Starlette/AnyIO deprecation warning; it does
not fail tests. Production deployment, security hardening, and Phase 2 business
features are outside this development infrastructure phase.
