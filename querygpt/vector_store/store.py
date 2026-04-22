"""
Vector store implementations.

Open/Closed     – pgvector, Chroma, Pinecone, Qdrant, etc. are new subclasses.
DIP             – agents call VectorStore, never a concrete class.
SRP             – each class only owns its own storage/search mechanics.
"""
from __future__ import annotations

import json
import logging
import math
import uuid
from abc import ABC, abstractmethod
from typing import Any, Optional

from querygpt.models import EmbeddedDocument, SearchResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class VectorStore(ABC):
    """Interface for vector similarity search."""

    @abstractmethod
    def upsert(self, doc: EmbeddedDocument) -> None:
        """Insert or update a document."""

    @abstractmethod
    def upsert_batch(self, docs: list[EmbeddedDocument]) -> None:
        """Batch upsert (default: loop; override for efficiency)."""

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_metadata: Optional[dict[str, Any]] = None,
    ) -> list[SearchResult]:
        """Return top-k most similar documents, optionally filtered by metadata."""

    @abstractmethod
    def delete(self, doc_id: str) -> None:
        """Remove a document by ID."""

    @abstractmethod
    def count(self) -> int:
        """Return total number of stored documents."""


class VectorStoreError(Exception):
    """Raised when a vector store operation fails."""


# ---------------------------------------------------------------------------
# pgvector – PostgreSQL-backed store (requires pgvector extension)
# ---------------------------------------------------------------------------

class PgVectorStore(VectorStore):
    """
    Stores embeddings in PostgreSQL using the pgvector extension.
    Schema is auto-created on first use.

    Extending to a different table: pass a custom table_name.
    """

    DDL = """
    CREATE EXTENSION IF NOT EXISTS vector;

    CREATE TABLE IF NOT EXISTS {table} (
        id          TEXT PRIMARY KEY,
        content     TEXT NOT NULL,
        embedding   VECTOR({dim}),
        metadata    JSONB DEFAULT '{{}}'::jsonb,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS {table}_embedding_idx
        ON {table} USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """

    def __init__(
        self,
        connector,          # DatabaseConnector – avoid circular import with string hint
        dimension: int = 1536,
        table_name: str = "querygpt_embeddings",
    ) -> None:
        self._db = connector
        self._dim = dimension
        self._table = table_name
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        ddl = self.DDL.format(table=self._table, dim=self._dim)
        for stmt in ddl.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                self._db.execute(stmt + ";")

    # ------------------------------------------------------------------

    def upsert(self, doc: EmbeddedDocument) -> None:
        emb_str = "[" + ",".join(str(v) for v in doc.embedding) + "]"
        self._db.execute(
            f"""
            INSERT INTO {self._table} (id, content, embedding, metadata)
            VALUES (%s, %s, %s::vector, %s)
            ON CONFLICT (id) DO UPDATE
                SET content   = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    metadata  = EXCLUDED.metadata
            """,
            (doc.id, doc.content, emb_str, json.dumps(doc.metadata)),
        )

    def upsert_batch(self, docs: list[EmbeddedDocument]) -> None:
        for doc in docs:
            self.upsert(doc)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_metadata: Optional[dict[str, Any]] = None,
    ) -> list[SearchResult]:
        emb_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        where_clause = ""
        params: list[Any] = [emb_str, top_k]

        if filter_metadata:
            conditions = []
            for k, v in filter_metadata.items():
                conditions.append(f"metadata->>'{k}' = %s")
                params.insert(-1, str(v))   # before top_k
            where_clause = "WHERE " + " AND ".join(conditions)

        rows = self._db.execute(
            f"""
            SELECT id, content, metadata,
                   1 - (embedding <=> %s::vector) AS score
            FROM   {self._table}
            {where_clause}
            ORDER  BY embedding <=> %s::vector
            LIMIT  %s
            """,
            [emb_str] + params,
            fetch=True,
        )

        results = []
        for row in rows:
            doc = EmbeddedDocument(
                id=row["id"],
                content=row["content"],
                embedding=[],   # not fetched back to save bandwidth
                metadata=row["metadata"] or {},
            )
            results.append(SearchResult(document=doc, score=float(row["score"])))
        return results

    def delete(self, doc_id: str) -> None:
        self._db.execute(f"DELETE FROM {self._table} WHERE id = %s", (doc_id,))

    def count(self) -> int:
        rows = self._db.execute(
            f"SELECT COUNT(*) AS n FROM {self._table}", fetch=True
        )
        return rows[0]["n"] if rows else 0


# ---------------------------------------------------------------------------
# InMemoryVectorStore – zero-dependency fallback (cosine similarity via math)
# ---------------------------------------------------------------------------

class InMemoryVectorStore(VectorStore):
    """
    Pure-Python in-memory store with cosine similarity.
    Useful for testing, small datasets, or when pgvector isn't available.
    Not suitable for production at scale.
    """

    def __init__(self) -> None:
        self._store: dict[str, EmbeddedDocument] = {}

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    def upsert(self, doc: EmbeddedDocument) -> None:
        self._store[doc.id] = doc

    def upsert_batch(self, docs: list[EmbeddedDocument]) -> None:
        for doc in docs:
            self._store[doc.id] = doc

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_metadata: Optional[dict[str, Any]] = None,
    ) -> list[SearchResult]:
        candidates = list(self._store.values())

        if filter_metadata:
            candidates = [
                d for d in candidates
                if all(d.metadata.get(k) == v for k, v in filter_metadata.items())
            ]

        scored = [
            SearchResult(document=d, score=self._cosine(query_embedding, d.embedding))
            for d in candidates
        ]
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]

    def delete(self, doc_id: str) -> None:
        self._store.pop(doc_id, None)

    def count(self) -> int:
        return len(self._store)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_vector_store(backend: str, **kwargs) -> VectorStore:
    registry: dict[str, type[VectorStore]] = {
        "pgvector": PgVectorStore,
        "memory":   InMemoryVectorStore,
    }
    cls = registry.get(backend.lower())
    if cls is None:
        raise ValueError(
            f"Unknown vector store backend '{backend}'. "
            f"Available: {list(registry.keys())}"
        )
    return cls(**kwargs)