# PostgreSQL

Compose owns PostgreSQL 17 and the existing `postgres-data` named volume.
Phase 1 creates no business tables or migrations; probes execute `SELECT 1`.
Future feature modules own their tables and repositories. Cross-module operations
call service functions rather than reading or writing another module's tables.
