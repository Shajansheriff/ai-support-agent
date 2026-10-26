# PostgreSQL

Compose owns the PostgreSQL 17 container and the `postgres-data` named volume.
No initialization SQL or business tables are needed for Phase 1. Probes use `SELECT 1`.
Future services will own their schemas/tables and migrations; other services must use
HTTP APIs rather than directly reading or writing another service's data.
