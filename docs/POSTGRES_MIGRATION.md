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
   - Centralizes connection setup and dialect-specific SQL helpers
   - Replaces scattered endpoint-local SQLite constructs with a single adapter surface
   - Keeps current SQLite behavior intact while reducing the eventual PostgreSQL porting footprint

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

## Export Bundle Contents
- `manifest.json` - export metadata, table counts, dependency-aware load order
- `schema-sqlite.sql` - reference snapshot of the current SQLite schema
- `tables/<table>.jsonl` - one JSON record per row in stable per-table order
- `README.txt` - quick reminder of how the bundle was produced

## Known Remaining Blockers
The readiness audit intentionally flags SQLite-specific constructs that still need refactoring, such as:
- `sqlite3` driver usage
- `PRAGMA` calls
- `AUTOINCREMENT`
- SQLite-only SQL functions or expressions

This is expected. The current tooling is for migration preparation, not a claim that PostgreSQL runtime support is already complete.
The important improvement is that those blockers are now concentrated in `storage.py` and `schema.sql`, rather than being distributed throughout `app.py`.

## Target Architecture
- Flask API stays the single business-rules layer
- PostgreSQL becomes the shared system of record
- Browser/phone UI remains primary for in-room work
- Tauri stays a companion client for printing, reporting, and workstation workflows

## Validation Expectations
Before cutting over to PostgreSQL:
- unit tests pass
- workflow/integration tests pass
- cage card rendering remains unchanged
- QR phone scan workflow still resolves in under facility expectations
- audit logging and protocol enforcement behave identically
