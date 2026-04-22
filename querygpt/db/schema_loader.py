"""
SchemaLoader – reads table metadata from any DatabaseConnector and
converts it into TableSchema domain objects.

Single Responsibility: only knows how to map raw DB metadata → domain model.
Depends on the abstraction (DatabaseConnector), not a concrete class.
"""
from __future__ import annotations

import logging
from typing import Optional

from querygpt.db.base import DatabaseConnector
from querygpt.models import ColumnInfo, TableSchema

logger = logging.getLogger(__name__)


class SchemaLoader:
    """Thin adapter: DatabaseConnector ↔ TableSchema."""

    def __init__(self, connector: DatabaseConnector) -> None:
        self._db = connector

    def load_table(self, table: str, schema: str = "public") -> Optional[TableSchema]:
        """Load a single table schema. Returns None if the table doesn't exist."""
        try:
            raw_cols = self._db.describe_table(table, schema)
        except Exception as exc:
            logger.warning("Could not describe %s.%s: %s", schema, table, exc)
            return None

        if not raw_cols:
            return None

        columns = [
            ColumnInfo(
                name=row["name"],
                data_type=row["data_type"],
                nullable=bool(row.get("nullable", True)),
                description=row.get("description"),
                is_primary_key=bool(row.get("is_primary_key", False)),
            )
            for row in raw_cols
        ]

        return TableSchema(
            table_name=table,
            schema_name=schema,
            columns=columns,
        )

    def load_all_tables(self, schema: str = "public") -> list[TableSchema]:
        """Load every table in *schema*."""
        tables = self._db.list_tables(schema)
        schemas: list[TableSchema] = []
        for t in tables:
            ts = self.load_table(t, schema)
            if ts:
                schemas.append(ts)
        logger.info("Loaded %d table schemas from schema '%s'.", len(schemas), schema)
        return schemas

    def load_tables_by_names(
        self, table_names: list[str], schema: str = "public"
    ) -> list[TableSchema]:
        """Load specific tables by name."""
        result = []
        for name in table_names:
            # Support "schema.table" notation
            if "." in name:
                s, t = name.split(".", 1)
            else:
                s, t = schema, name
            ts = self.load_table(t, s)
            if ts:
                result.append(ts)
        return result