# AI Customer Support Agent — Phase 1

A local infrastructure project for learning AI engineering and distributed systems.
The backend is a **modular monolith**: one FastAPI application, one Python package,
and one backend container, with clear feature boundaries inside it.

Phase 1 provides connectivity checks and placeholder interfaces. It does not
implement chat, tool calls, order/refund logic, approval workflows, authentication,
conversation persistence, SSE, queues, or durable execution.

## Architecture

| Component | Responsibility | Default host address |
| --- | --- | --- |
| customer-web | Placeholder chat and backend connectivity indicator | http://localhost:3000 |
| operator-web | Placeholder approvals and backend connectivity indicator | http://localhost:3001 |
| backend | FastAPI, health, PostgreSQL readiness, Ollama diagnostics | http://localhost:8000 |
| postgres | PostgreSQL 17 with a persistent named volume | localhost:5432 |
| Ollama | Native macOS model server; outside Docker | http://localhost:11434 |

Compose starts **four containers** on its default bridge network. There is no
separate gateway or worker. The browser calls the backend directly using
`VITE_API_BASE_URL`. Within the backend, modules will communicate through Python
service functions, not HTTP calls to themselves.

Inside a container, `localhost` means that container. The backend reaches the
database at `postgres:5432` using Compose DNS. It reaches native macOS Ollama at
`host.docker.internal:11434`, Docker Desktop's address for the Mac. Ollama runs
natively for Apple Silicon GPU acceleration; it is not installed in Docker.
See the [official Ollama FAQ](https://docs.ollama.com/faq).

## Backend organization and growth

- `app/main.py`: application factory, CORS, logging, router registration.
- `app/core`: configuration read from environment at application construction and logging setup.
- `app/infrastructure`: asyncpg connectivity helper; later, shared database infrastructure.
- `app/integrations`: clients for external services, currently Ollama.
- `app/modules/system`: HTTP diagnostics, response schemas, and infrastructure checks.
- `app/modules/agent`, `orders`, `refunds`, `approvals`: feature boundaries with
  responsibility docstrings only until their use cases are implemented.

Add `router.py`, `schemas.py`, `service.py`, and `repository.py` to a feature only
when needed. Routers handle HTTP, services implement use cases, and repositories
own database access. A feature calls another feature's service functions rather
than importing its repository or accessing its tables. Infrastructure and external
clients must not import business modules. Avoid putting business logic into `core`.

The installable `support-backend` package is defined in `backend/pyproject.toml`.
Test dependencies are its `test` extra; root `requirements-dev.txt` installs that
extra without duplicating dependency versions. There are no business tables or
migrations in Phase 1. PostgreSQL checks use short-lived asyncpg connections and
`SELECT 1`, always closing successful connections even if the query fails.

There is no background worker or polling loop. Future durable execution needs an
explicit persistence, recovery, and scheduling design. Ordinary FastAPI background
tasks alone would not provide durable execution across restarts. That design is
outside this phase.

## Prerequisites and startup

- Docker Desktop for Apple Silicon, running (`docker info` must work).
- Optional native tools: Python 3.12+ for unit tests; Node 22.12+ and npm for UI builds.
- Python 3 for the standard-library smoke script.
- Optional [Ollama for macOS](https://ollama.com/download/mac); no model is required.

From the repository root:

```bash
cp .env.example .env  # Only on first setup; preserve an existing .env
docker compose up --build
```

Defaults also permit startup without `.env`. These credentials are for local
development. `.env` is ignored by Git. If changing database credentials, also
update `DATABASE_URL` with matching URL-encoded credentials. Existing database
volumes retain their original users/passwords; changing environment variables does
not change credentials already stored by PostgreSQL.

For background operation:

```bash
docker compose up --build -d --wait --wait-timeout 120 --remove-orphans
docker compose ps
```

The backend has one Uvicorn application process with development reload (the
reload watcher is not another application worker). All four containers have health
checks and `unless-stopped` restart policies. Initial backend startup waits for
PostgreSQL health; later outages cause `/ready` to return 503 while `/health`
continues responding. Ollama is optional and never blocks startup or readiness.

The images support native ARM64 builds. Frontend images use `npm ci` and committed
lockfiles. Python source and frontend source/config are mounted for development;
container `node_modules` remains in the image to avoid host/container conflicts.
Rebuild after dependency changes. Recreate containers after environment changes.

## API contracts

All endpoints live on backend port 8000. No legacy service ports or proxies remain.

| Endpoint | Response and meaning |
| --- | --- |
| `GET /health` | `{"service":"backend","status":"healthy"}`; process liveness only. |
| `GET /ready` | `service`, `status` (`ready`/`not_ready`), `database` (`connected`/`unavailable`); HTTP 200 or 503 following `SELECT 1`. |
| `GET /integrations/ollama/health` | `reachable`, `available_models`, `configured_model`, `model_installed`, `error`; diagnostics return HTTP 200 even when disconnected. |
| `GET /api/system/status` | `status` (`healthy`/`degraded`), `database` (`connected`/`unavailable`), `ollama` (the same diagnostics object). HTTP 200; overall health depends only on PostgreSQL. |

Status checks query PostgreSQL and Ollama concurrently with bounded timeouts.
Ollama offline or a missing model does not degrade infrastructure readiness.
The UIs poll `/health` every ten seconds and display “Backend: connected” when its
contract matches; that indicator is liveness, not full dependency readiness.

## Native Ollama

Install and open the macOS application, or run `ollama serve`. Do not launch a
second server if the app already occupies port 11434. Model download is optional:

```bash
ollama pull qwen3:4b
ollama list
curl http://localhost:11434/api/tags
curl http://localhost:8000/integrations/ollama/health
```

If host requests work but Docker requests fail, adjust Ollama's bind address.
For the macOS app, run the following, then fully quit and reopen Ollama:

```bash
launchctl setenv OLLAMA_HOST "0.0.0.0:11434"
```

For a CLI server, stop the old server and run:

```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

Binding all interfaces can expose this unauthenticated API on your network; use
a trusted network and firewall settings. Undo the app setting with
`launchctl unsetenv OLLAMA_HOST` and restart the app. See
[Ollama's macOS configuration instructions](https://docs.ollama.com/faq#setting-environment-variables-on-mac).

## Tests and health checks

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost:8000/api/system/status
python3 scripts/smoke.py
```

Smoke tests check backend liveness, database readiness, system diagnostics, both
frontend HTML responses, and the Ollama contract. They allow up to 60 seconds for
startup and exit nonzero on failure. Add `--ollama online` to require reachable
Ollama, or `--operator-port 13001` when using that local port override.

Force Ollama offline without stopping your native server or deleting database data:

```bash
docker compose down
docker compose -f compose.yaml -f scripts/compose.ollama-offline.yaml up -d --wait --wait-timeout 120
python3 scripts/smoke.py --ollama offline
# Restore the normal backend configuration:
docker compose up -d --wait --wait-timeout 120
```

Unit tests need no Docker or Ollama:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

They cover liveness, CORS, database failure/recovery and cleanup, optional Ollama,
malformed responses, timeouts, and aggregate diagnostics. Build each UI with:

```bash
(cd apps/customer-web && npm ci && npm run build)
(cd apps/operator-web && npm ci && npm run build)
```

To run only the backend on the host after installing dependencies:

```bash
DATABASE_URL=postgresql://support:support_dev_password@localhost:5432/support \
OLLAMA_BASE_URL=http://localhost:11434 \
uvicorn app.main:app --reload --port 8000
```

Use the configured host PostgreSQL port if overridden, and stop the containerized
backend to free port 8000. Compose reads `.env`; standalone Python does not load
it automatically. Host processes cannot resolve Compose's `postgres` hostname.

## Logs, stopping, and data preservation

```bash
docker compose logs -f backend
docker compose logs --tail=100 postgres
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1"'
docker compose stop          # Keep containers and volume
docker compose start         # Resume existing containers
docker compose down          # Remove containers/network; preserve volume
docker compose up -d         # Reuse preserved PostgreSQL data
```

The project name remains `ai-support-agent`, and PostgreSQL retains the
`postgres-data` named volume at `/var/lib/postgresql/data`. To intentionally erase
**all project database data** and initialize again:

```bash
docker compose down --volumes
docker compose up --build -d
```

When upgrading from the microservice version, preserve `.env` credentials and
port overrides, rename `VITE_GATEWAY_URL` to `VITE_API_BASE_URL`, and remove the
four internal service URLs and `WORKER_CHECK_INTERVAL`. Then run
`docker compose up --build -d --wait --remove-orphans`. This removes obsolete
service containers without deleting the PostgreSQL volume. Frontend health checks
must use the new backend contract; ports 8001–8004 are no longer exposed.

## Troubleshooting and local overrides

- **Docker unavailable:** start Docker Desktop; check `docker info` and `docker context ls`.
- **PostgreSQL port occupied:** set `POSTGRES_PORT=15432` in `.env`. Only host clients
  use this port; Docker's `DATABASE_URL` must still use `postgres:5432`.
- **Operator port occupied:** set `OPERATOR_WEB_PORT=13001`, add
  `http://localhost:13001` to `CORS_ORIGINS`, open that URL, and pass
  `--operator-port 13001` to smoke tests. The container still listens on 3001.
- **UI disconnected:** check the browser's API URL and CORS origin. The browser
  uses localhost:8000, not a Docker hostname.
- **Database unavailable:** inspect `/ready` and PostgreSQL logs. Verify credentials
  match the existing volume; do not reset non-disposable data to fix configuration.
- **Ollama disconnected:** check host `/api/tags`, bind address, firewall, VPN, and
  Docker Desktop networking. Probe from the backend with:
  `docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags', timeout=3).read().decode())"`.
- **Hot reload not working:** check Docker Desktop file sharing for this repository.
  Dependency changes require an image rebuild.

This machine's ignored `.env` preserves PostgreSQL port **15432**, operator port
**13001**, and its corresponding CORS origin. Committed defaults remain 5432 and
3001. Neither existing host services nor their data need to be stopped or changed.

## Repository tree

Generated dependencies, build output, caches, `.git`, and `.env` are omitted.

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
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── logging.py
│   │   ├── infrastructure/
│   │   │   ├── __init__.py
│   │   │   └── database.py
│   │   ├── integrations/
│   │   │   ├── __init__.py
│   │   │   └── ollama.py
│   │   ├── modules/
│   │   │   ├── agent/
│   │   │   │   └── __init__.py
│   │   │   ├── approvals/
│   │   │   │   └── __init__.py
│   │   │   ├── orders/
│   │   │   │   └── __init__.py
│   │   │   ├── refunds/
│   │   │   │   └── __init__.py
│   │   │   ├── system/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py
│   │   │   │   ├── schemas.py
│   │   │   │   └── service.py
│   │   │   └── __init__.py
│   │   ├── __init__.py
│   │   └── main.py
│   ├── Dockerfile
│   └── pyproject.toml
├── infra/
│   └── postgres/
│       └── README.md
├── scripts/
│   ├── compose.ollama-offline.yaml
│   └── smoke.py
├── tests/
│   └── test_infrastructure.py
├── .dockerignore
├── .env.example
├── .gitignore
├── README.md
├── compose.yaml
├── pytest.ini
└── requirements-dev.txt
```

## Monolith validation results

Validated after this refactor on Apple Silicon with Python 3.12 and Docker Desktop:

- 19 updated Pytest cases passed; one upstream Starlette/AnyIO deprecation warning.
- Both TypeScript/Vite production builds passed.
- Exactly four Compose containers reached healthy status; obsolete service
  containers were removed with `--remove-orphans`.
- Live smoke tests passed with native Ollama online and with Ollama forced offline.
- Stopping PostgreSQL returned HTTP 503 from `/ready` and degraded system status,
  while backend liveness continued to return healthy. Readiness recovered on restart.
- A disposable probe row survived the architecture migration and full container
  recreation; its test table was removed afterward.
- Both browser UIs displayed “Backend: connected” with no captured console warnings
  or errors. Existing host port overrides remained in effect.

Native Ollama was reachable but `qwen3:4b` was not installed, correctly reported
without failing infrastructure checks. No model was downloaded. Normal Ollama
configuration was restored and the four-container stack was left running.
