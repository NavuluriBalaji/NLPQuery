from querygpt.config import DatabaseConfig
from querygpt.db.base import DatabaseConnector
from querygpt.db.postgres import PostgresConnector
from querygpt.db.oracle import OracleConnector


def build_database_connector(
    engine: str,
    config: DatabaseConfig,
) -> DatabaseConnector:
    """
    Factory responsible for creating the appropriate database connector.
    """

    engine = engine.lower()

    if engine == "postgres":
        return PostgresConnector(config)

    if engine == "oracle":
        return OracleConnector(config)

    raise ValueError(f"Unsupported database engine: {engine}")