# PostgreSQL Migration Guide

## Goal
Move Murisphere from a single-node SQLite runtime to a centralized PostgreSQL-backed deployment that can serve:
- browser/phone SaaS users
- Tauri desktop users
- multi-user concurrent facility operations
- enterprise backup, access-control, and disaster-recovery requirements

## Current State
- Runtime database: SQLite
- Primary application server: Flask in `app.py`
- Desktop shell: Tauri companion in `desktop/`
- Shared enterprise target: centralized API + PostgreSQL

## What Is Implemented Today
Two migration-prep tools are now in the repo:

1. `postgres_readiness_audit.py`
   - Scans the codebase and schema for SQLite-specific constructs
   - Exits non-zero while blockers still exist
   - Produces a JSON report suitable for CI or migration planning

2. `postgres_export_bundle.py`
   - Reads the current SQLite database
   - Discovers all tables and foreign-key dependencies
   - Exports table data to dependency-aware `JSONL` files
   - Writes a manifest and copies the current SQLite schema for reference

There is also an initial runtime abstraction layer:

3. `storage.py`
   - Dispatches runtime storage by dialect
   - Replaces scattered endpoint-local SQLite constructs with a single adapter surface
   - Keeps current SQLite behavior intact while reducing the eventual PostgreSQL porting footprint
   - Supports `MURISPHERE_DB_DIALECT=postgres` and `MURISPHERE_DATABASE_URL=...`
   - Delegates to `storage_sqlite.py` and `storage_postgres.py`

4. `storage_postgres.py`
   - Holds PostgreSQL-specific connection, query translation, and cursor-wrapper logic
   - Keeps PostgreSQL runtime concerns out of the generic dispatcher

5. `storage_sqlite.py`
   - Keeps legacy SQLite compatibility isolated from the PostgreSQL runtime path

6. `schema_postgres.sql`
   - Explicit checked-in PostgreSQL bootstrap schema
   - Generated from `schema.sql` via `generate_postgres_schema.py`
   - Removes SQLite-only DDL such as `PRAGMA` and `AUTOINCREMENT`

## Recommended Migration Sequence
1. Run the readiness audit.
2. Remove SQLite-specific SQL and driver assumptions from runtime code.
3. Introduce a database abstraction layer or query adapter for backend storage.
4. Add PostgreSQL migrations and a target schema.
5. Export a representative SQLite environment with `postgres_export_bundle.py`.
6. Build an importer/ETL step into PostgreSQL staging.
7. Run application and workflow tests against PostgreSQL.
8. Switch centralized deployments to PostgreSQL.
9. Keep desktop and browser clients pointed at the same centralized API.

## Commands
Readiness audit:
```bash
python3 postgres_readiness_audit.py --out docs/test_reports/POSTGRES_READINESS.json
```

Logical export:
```bash
python3 postgres_export_bundle.py --db murisphere.db --out dist/postgres-bundle
```

Runtime configuration bridge:
```bash
export MURISPHERE_DB_DIALECT=postgres
export MURISPHERE_DATABASE_URL=postgresql://user:pass@host:5432/murisphere
python3 app.py
```

## Export Bundle Contents
- `manifest.json` - export metadata, table counts, dependency-aware load order
- `schema-sqlite.sql` - reference snapshot of the current SQLite schema
- `tables/<table>.jsonl` - one JSON record per row in stable per-table order
- `README.txt` - quick reminder of how the bundle was produced

## Readiness Audit
The PostgreSQL readiness audit now passes for the Postgres-target runtime path.

That means:
- `app.py`
- `storage.py`
- `storage_postgres.py`
- `schema_postgres.sql`

no longer contain the specific SQLite-only constructs tracked by the audit.

SQLite compatibility still exists in `storage_sqlite.py`, but that is no longer treated as a blocker for the PostgreSQL runtime path.
The current PostgreSQL bootstrap is explicit and versioned, but a production cutover should still move to first-class Postgres-native migrations.

## Target Architecture
- Flask API stays the single business-rules layer
- PostgreSQL becomes the shared system of record
- Browser/phone UI remains primary for in-room work
- Tauri stays a companion client for printing, reporting, and workstation workflows

## Validation Expectations
Before cutting over to PostgreSQL:
- unit tests pass
- dedicated PostgreSQL integration tests pass against a live service
- workflow/integration tests pass
- cage card rendering remains unchanged
- QR phone scan workflow still resolves in under facility expectations
- audit logging and protocol enforcement behave identically
