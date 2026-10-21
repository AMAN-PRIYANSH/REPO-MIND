"""PostgreSQL + pgvector `VectorStore` backend (CP4 deliverable 2, ADR-007).

Uses `psycopg` (v3) and the `pgvector` Python client. The schema is created by the migration
file in `migrations/`; `PgVectorStore(..., migrate=True)` applies it (idempotent). The
contract is the one documented in `vectorstore.py`: cosine similarity = 1 - (a <=> b), ties
by chunk_id, `embedding_model` required for search, at least one filter for delete.
"""

import re
from pathlib import Path

import numpy as np

from vulntrace.retrieval.vectorstore import (
    FILTER_FIELDS,
    SearchHit,
    VectorRecord,
    VectorStore,
    VectorStoreError,
    check_filters,
    check_record,
)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
DEFAULT_TABLE = "code_chunks"
_TABLE_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_META_COLS = [f for f in FILTER_FIELDS if f not in ("variant", "embedding_model")]


def migration_sql(table: str = DEFAULT_TABLE) -> list[tuple[str, str]]:
    """[(version, sql)] for every migration file, in order, with the table name filled in."""
    if not _TABLE_RE.match(table):
        raise VectorStoreError(f"invalid table name {table!r}")
    return [(p.stem, p.read_text(encoding="utf-8").replace("{table}", table))
            for p in sorted(MIGRATIONS_DIR.glob("*.sql"))]


class PgVectorStore(VectorStore):
    def __init__(self, dsn: str, table: str = DEFAULT_TABLE, migrate: bool = True, connect_timeout: int = 5):
        import psycopg
        from pgvector.psycopg import register_vector

        if not _TABLE_RE.match(table):
            raise VectorStoreError(f"invalid table name {table!r}")
        self.table = table
        self._conn = psycopg.connect(dsn, connect_timeout=connect_timeout, autocommit=True)
        if migrate:
            self.migrate()
        register_vector(self._conn)

    def migrate(self) -> None:
        with self._conn.cursor() as cur:
            for version, sql in migration_sql(self.table):
                cur.execute(sql)
                cur.execute("INSERT INTO vt_schema_migrations (version) VALUES (%s) ON CONFLICT DO NOTHING",
                            (f"{self.table}:{version}",))

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _where(filters: dict[str, str]) -> tuple[str, list]:
        if not filters:
            return "", []
        keys = sorted(filters)
        return " WHERE " + " AND ".join(f"{k} = %s" for k in keys), [filters[k] for k in keys]

    def upsert(self, records: list[VectorRecord]) -> None:
        if not records:
            return
        cols = ["chunk_id", "variant", "embedding_model", *_META_COLS, "embedding"]
        sql = (f"INSERT INTO {self.table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
               f"ON CONFLICT (chunk_id, variant, embedding_model) DO UPDATE SET "
               + ", ".join(f"{c} = EXCLUDED.{c}" for c in cols[3:]))
        rows = []
        for r in records:
            check_record(r)
            m = r.metadata
            rows.append([r.chunk_id, m["variant"], m["embedding_model"], *[m.get(c, "") for c in _META_COLS],
                         np.asarray(r.vector, dtype=np.float32).reshape(-1)])
        with self._conn.cursor() as cur:
            cur.executemany(sql, rows)

    def search(self, vector: np.ndarray, filters: dict[str, str], k: int) -> list[SearchHit]:
        check_filters(filters, for_search=True)
        if k <= 0:
            return []
        where, params = self._where(filters)
        q = np.asarray(vector, dtype=np.float32).reshape(-1)
        sql = (f"SELECT chunk_id, 1 - (embedding <=> %s) AS score, variant, embedding_model, "
               f"{', '.join(_META_COLS)} FROM {self.table}{where} "
               f"ORDER BY embedding <=> %s, chunk_id, variant LIMIT %s")
        import psycopg

        try:
            with self._conn.cursor() as cur:
                cur.execute(sql, [q, *params, q, k])
                rows = cur.fetchall()
        except psycopg.errors.DataException as exc:  # e.g. "different vector dimensions"
            raise VectorStoreError(str(exc).strip()) from exc
        out = []
        for row in rows:
            meta = {"variant": row[2], "embedding_model": row[3]}
            meta.update({c: v for c, v in zip(_META_COLS, row[4:]) if v != ""})
            out.append(SearchHit(row[0], float(row[1]), meta))
        return out

    def delete(self, filters: dict[str, str]) -> int:
        check_filters(filters, for_search=False)
        where, params = self._where(filters)
        with self._conn.cursor() as cur:
            cur.execute(f"DELETE FROM {self.table}{where}", params)
            return cur.rowcount

    def count(self, filters: dict[str, str] | None = None) -> int:
        if filters:
            check_filters(filters, for_search=False)
        where, params = self._where(filters or {})
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {self.table}{where}", params)
            return int(cur.fetchone()[0])

    def drop_table(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {self.table}")
            cur.execute("DELETE FROM vt_schema_migrations WHERE version LIKE %s", (f"{self.table}:%",))
