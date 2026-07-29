"""
Oracle connector – concrete implementation of DatabaseConnector.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

import oracledb

from querygpt.config import DatabaseConfig
from querygpt.db.base import DatabaseConnector, DatabaseError

logger = logging.getLogger(__name__)


class OracleConnector(DatabaseConnector):

    def __init__(self, cfg: DatabaseConfig) -> None:
        self._cfg = cfg
        self._conn: oracledb.Connection | None = None

    # ---------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------

    def connect(self) -> None:
        if self._conn:
            return

        try:
            dsn = f"{self._cfg.host}:{self._cfg.port}/{self._cfg.name}"

            self._conn = oracledb.connect(
                user=self._cfg.user,
                password=self._cfg.password,
                dsn=dsn
            )

            logger.info(
                "Oracle connected (%s@%s:%s/%s)",
                self._cfg.user,
                self._cfg.host,
                self._cfg.port,
                self._cfg.name
            )

        except Exception as exc:
            raise DatabaseError(f"Cannot connect to Oracle: {exc}") from exc

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ---------------------------------------------------------
    # Query execution
    # ---------------------------------------------------------

    def execute(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
        *,
        fetch: bool = False,
    ) -> list[dict[str, Any]]:

        if self._conn is None:
            raise DatabaseError("OracleConnector.connect() was not called.")

        try:

            cursor = self._conn.cursor()

            cursor.execute(sql, params or [])

            if fetch:

                columns = [c[0].lower() for c in cursor.description]

                rows = []

                for r in cursor.fetchall():
                    rows.append(dict(zip(columns, r)))

                return rows

            self._conn.commit()

            return []

        except Exception as exc:

            self._conn.rollback()

            raise DatabaseError(f"Query failed: {exc}\nSQL: {sql}") from exc

    # ---------------------------------------------------------
    # Introspection
    # ---------------------------------------------------------

    def list_schemas(self) -> list[str]:

        rows = self.execute(
            """
            SELECT username AS schema_name
            FROM all_users
            ORDER BY username
            """,
            fetch=True,
        )

        return [r["schema_name"] for r in rows]

    def list_tables(self, schema: str) -> list[str]:

        rows = self.execute(
            """
            SELECT table_name
            FROM all_tables
            WHERE owner = :1
            ORDER BY table_name
            """,
            [schema.upper()],
            fetch=True,
        )

        return [r["table_name"] for r in rows]

    def describe_table(self, table: str, schema: str):

        rows = self.execute(
            """
            SELECT
                column_name AS name,
                data_type,
                CASE nullable
                    WHEN 'Y' THEN 1
                    ELSE 0
                END AS nullable
            FROM all_tab_columns
            WHERE owner = :1
              AND table_name = :2
            ORDER BY column_id
            """,
            [schema.upper(), table.upper()],
            fetch=True,
        )

        return rows

    def describe_foreign_keys(self, table: str, schema: str):

        rows = self.execute(
            """
            SELECT
                acc.column_name,
                ac_r.table_name referenced_table,
                acc_r.column_name referenced_column
            FROM all_constraints ac
            JOIN all_cons_columns acc
                ON ac.constraint_name = acc.constraint_name
            JOIN all_constraints ac_r
                ON ac.r_constraint_name = ac_r.constraint_name
            JOIN all_cons_columns acc_r
                ON ac_r.constraint_name = acc_r.constraint_name
            WHERE ac.constraint_type='R'
            AND ac.owner=:1
            AND ac.table_name=:2
            """,
            [schema.upper(), table.upper()],
            fetch=True,
        )

        return rows

    def ping(self):

        try:
            self.execute("SELECT 1 FROM dual", fetch=True)
            return True
        except DatabaseError:
            return False