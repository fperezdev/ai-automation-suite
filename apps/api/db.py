"""Acceso a Postgres: pool de conexiones + migraciones idempotentes."""
from __future__ import annotations

import os
import pathlib
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DSN = os.getenv("DATABASE_URL", "postgresql://suite:suite@postgres:5432/suite")
MIGRATIONS = pathlib.Path(os.getenv("MIGRATIONS_DIR", "/db/migrations"))

pool = ConnectionPool(DSN, min_size=1, max_size=8, kwargs={"row_factory": dict_row})


def conn():
    return pool.connection()


def query(sql: str, params: tuple | dict | None = None) -> list[dict]:
    with pool.connection() as c, c.cursor() as cur:
        cur.execute(sql, params or {})
        return cur.fetchall() if cur.description else []


def one(sql: str, params: tuple | dict | None = None) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple | dict | None = None) -> dict | None:
    with pool.connection() as c, c.cursor() as cur:
        cur.execute(sql, params or {})
        row = cur.fetchone() if cur.description else None
        c.commit()
        return row


def migrate() -> list[str]:
    """Aplica db/migrations/*.sql en orden, una sola vez (tabla schema_migrations)."""
    applied: list[str] = []
    with pool.connection() as c, c.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
                         version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())""")
        c.commit()
        cur.execute("SELECT version FROM schema_migrations")
        done = {r["version"] for r in cur.fetchall()}
        for f in sorted(MIGRATIONS.glob("*.sql")):
            if f.name in done:
                continue
            cur.execute(f.read_text())
            cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (f.name,))
            c.commit()
            applied.append(f.name)
    return applied
