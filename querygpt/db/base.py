"""
Abstract database connector.

Open/Closed Principle  – open for extension (MySQL, SQLite, BigQuery, etc.),
                          closed for modification of existing behaviour.
Dependency Inversion   – high-level pipeline depends on this abstraction,
                          NOT on a concrete psycopg2/SQLAlchemy class.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Generator, Sequence


class DatabaseConnector(ABC):
    """
    Minimal interface every database backend must satisfy.
    Extend this for MySQL, SQLite, BigQuery, Snowflake, etc.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def connect(self) -> None:
        """Establish connection / warm pool."""

    @abstractmethod
    def disconnect(self) -> None:
        """Release all connections / close pool."""

    @contextmanager
    def managed(self) -> Generator["DatabaseConnector", None, None]:
        """Context manager helper: connect → yield self → disconnect."""
        self.connect()
        try:
            yield self
        finally:
            self.disconnect()

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------

    @abstractmethod
    def execute(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
        *,
        fetch: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Execute *sql* with optional *params*.
        If *fetch* is True, return rows as list-of-dicts; otherwise return [].
        Raises DatabaseError on failure.
        """

    # ------------------------------------------------------------------
    # Introspection helpers  (used by SchemaLoader)
    # ------------------------------------------------------------------

    @abstractmethod
    def list_schemas(self) -> list[str]:
        """Return all non-system schema names."""

    @abstractmethod
    def list_tables(self, schema: str = "public") -> list[str]:
        """Return all table names in *schema*."""

    @abstractmethod
    def describe_table(self, table: str, schema: str = "public") -> list[dict[str, Any]]:
        """
        Return column metadata for *schema.table*.
        Each dict should contain at least: name, data_type, nullable.
        """

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @abstractmethod
    def ping(self) -> bool:
        """Return True if the database is reachable."""


class DatabaseError(Exception):
    """Raised when a database operation fails."""