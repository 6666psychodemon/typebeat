# Migrations

Canonical DDL lives in `sql/schema/`. When the catalog or auth model changes:

1. Add a new numbered file under `sql/schema/` (or a dated migration here).
2. Update `producer_harvester_v2.ensure_schema` / `radio/auth_db.init_db()` if the app bootstraps SQLite locally.
3. Apply the same SQL to **onthebeat-dev** (Turso) first, then **onthebeat** (prod) after verification.

Turso workflow details: [`docs/GITHUB_TURSO_WORKFLOW.md`](../../docs/GITHUB_TURSO_WORKFLOW.md).
