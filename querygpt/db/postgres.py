"""
PostgreSQL connector – concrete implementation of DatabaseConnector.

Single Responsibility: owns ONLY the psycopg2 connection lifecycle
                       and raw query execution.
"""
from __future__ import annotations

import logging
from typing import Any, Sequence

import psycopg2
import psycopg2.extras
from psycopg2 import pool as pg_pool

from querygpt.config import DatabaseConfig
from querygpt.db.base import DatabaseConnector, DatabaseError

logger = logging.getLogger(__name__)


class PostgresConnector(DatabaseConnector):
    """
    Thread-safe PostgreSQL connector backed by a psycopg2 connection pool.

    Extending to MySQL / SQLite:  create a parallel sibling class that
    implements DatabaseConnector – zero changes required in agents or pipeline.
    """

    def __init__(self, cfg: DatabaseConfig) -> None:
        self._cfg = cfg
        self._pool: pg_pool.ThreadedConnectionPool | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        if self._pool is not None:
            return  # already connected
        try:
            self._pool = pg_pool.ThreadedConnectionPool(
                minconn=self._cfg.pool_min,
                maxconn=self._cfg.pool_max,
                host=self._cfg.host,
                port=self._cfg.port,
                dbname=self._cfg.name,
                user=self._cfg.user,
                password=self._cfg.password,
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
            logger.info(
                "PostgreSQL pool connected (%s@%s:%s/%s)",
                self._cfg.user,
                self._cfg.host,
                self._cfg.port,
                self._cfg.name,
            )
        except psycopg2.OperationalError as exc:
            raise DatabaseError(f"Cannot connect to PostgreSQL: {exc}") from exc

    def disconnect(self) -> None:
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("PostgreSQL pool closed.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_conn(self) -> psycopg2.extensions.connection:
        if self._pool is None:
            raise DatabaseError("PostgresConnector.connect() was not called.")
        return self._pool.getconn()

    def _put_conn(self, conn: psycopg2.extensions.connection) -> None:
        if self._pool:
            self._pool.putconn(conn)

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------

    def execute(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
        *,
        fetch: bool = False,
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                conn.commit()
                if fetch:
                    rows = cur.fetchall()
                    return [dict(r) for r in rows]
                return []
        except psycopg2.Error as exc:
            conn.rollback()
            raise DatabaseError(f"Query failed: {exc}\nSQL: {sql}") from exc
        finally:
            self._put_conn(conn)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_schemas(self) -> list[str]:
        rows = self.execute(
            """
            SELECT schema_name
            FROM   information_schema.schemata
            WHERE  schema_name NOT IN ('pg_catalog', 'information_schema',
                                       'pg_toast', 'pg_temp_1')
            ORDER  BY schema_name
            """,
            fetch=True,
        )
        return [r["schema_name"] for r in rows]

    def list_tables(self, schema: str = "public") -> list[str]:
        rows = self.execute(
            """
            SELECT table_name
            FROM   information_schema.tables
            WHERE  table_schema = %s
              AND  table_type   = 'BASE TABLE'
            ORDER  BY table_name
            """,
            (schema,),
            fetch=True,
        )
        return [r["table_name"] for r in rows]

    def describe_table(self, table: str, schema: str = "public") -> list[dict[str, Any]]:
        rows = self.execute(
            """
            SELECT
                c.column_name                          AS name,
                c.data_type                            AS data_type,
                c.is_nullable = 'YES'                  AS nullable,
                col_description(
                    (quote_ident(c.table_schema)
                     || '.' || quote_ident(c.table_name))::regclass::oid,
                    c.ordinal_position
                )                                      AS description,
                CASE WHEN pk.column_name IS NOT NULL
                     THEN TRUE ELSE FALSE END          AS is_primary_key
            FROM   information_schema.columns c
            LEFT JOIN (
                SELECT ku.column_name
                FROM   information_schema.table_constraints tc
                JOIN   information_schema.key_column_usage  ku
                       ON  tc.constraint_name = ku.constraint_name
                       AND tc.table_schema    = ku.table_schema
                WHERE  tc.constraint_type = 'PRIMARY KEY'
                  AND  tc.table_name   = %s
                  AND  tc.table_schema = %s
            ) pk ON pk.column_name = c.column_name
            WHERE  c.table_name   = %s
              AND  c.table_schema = %s
            ORDER  BY c.ordinal_position
            """,
            (table, schema, table, schema),
            fetch=True,
        )
        return rows

    def ping(self) -> bool:
        try:
            self.execute("SELECT 1", fetch=True)
            return True
        except DatabaseError:
            return False