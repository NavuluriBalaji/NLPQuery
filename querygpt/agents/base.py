"""
Abstract Agent base and the RAGIndex helper used by all agents.

Interface Segregation – each agent's Input/Output types are defined in models.py.
Single Responsibility  – RAGIndex only handles embedding + retrieval orchestration.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from querygpt.embeddings.providers import EmbeddingProvider
from querygpt.models import EmbeddedDocument, SQLSample, TableSchema
from querygpt.vector_store.store import VectorStore

# Generic agent pattern
I = TypeVar("I")
O = TypeVar("O")


class Agent(ABC, Generic[I, O]):
    """
    All QueryGPT agents share this interface.
    Liskov: every Agent[I,O] can be swapped for another Agent[I,O]
            with identical I/O contracts.
    """

    @abstractmethod
    def run(self, input_: I) -> O:
        """Execute the agent and return a typed output."""


# ---------------------------------------------------------------------------
# RAGIndex – shared retrieval logic used by agents
# ---------------------------------------------------------------------------

class RAGIndex:
    """
    Manages two vector indexes:
      - schema_store  : table schemas (TableSchema → DDL string)
      - sample_store  : golden SQL samples (SQLSample → question)

    SRP: RAGIndex only knows about indexing and retrieval.
         It does NOT know about LLMs, agents, or the pipeline.
    """

    def __init__(
        self,
        schema_store: VectorStore,
        sample_store: VectorStore,
        embedder: EmbeddingProvider,
    ) -> None:
        self._schema_store = schema_store
        self._sample_store = sample_store
        self._embedder = embedder

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_schema(self, table: TableSchema, workspace: str | None = None) -> None:
        content = f"Table: {table.full_name}\n{table.to_ddl()}"
        if table.description:
            content = f"{table.description}\n{content}"
        doc = EmbeddedDocument(
            id=f"schema::{table.full_name}",
            content=content,
            embedding=self._embedder.embed(content),
            metadata={
                "type": "schema",
                "table": table.full_name,
                "workspace": workspace or "",
            },
        )
        self._schema_store.upsert(doc)

    def index_sample(self, sample: SQLSample) -> None:
        content = sample.question
        doc = EmbeddedDocument(
            id=f"sample::{uuid.uuid4().hex[:8]}::{sample.question[:30]}",
            content=content,
            embedding=self._embedder.embed(content),
            metadata={
                "type": "sample",
                "sql": sample.sql,
                "tables": ",".join(sample.tables_used),
                "workspace": sample.workspace or "",
                "description": sample.description or "",
            },
        )
        self._sample_store.upsert(doc)

    def index_schemas_batch(
        self, tables: list[TableSchema], workspace: str | None = None
    ) -> None:
        for t in tables:
            self.index_schema(t, workspace)

    def index_samples_batch(self, samples: list[SQLSample]) -> None:
        for s in samples:
            self.index_sample(s)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def search_schemas(
        self,
        query: str,
        top_k: int = 5,
        workspace: str | None = None,
    ) -> list[str]:
        """Return list of table full_names ranked by relevance."""
        q_emb = self._embedder.embed(query)
        filter_ = {"workspace": workspace} if workspace else None
        results = self._schema_store.search(q_emb, top_k=top_k, filter_metadata=filter_)
        if not results and filter_ is not None:
            # Fallback: if strict workspace filter yields 0, search everywhere
            results = self._schema_store.search(q_emb, top_k=top_k, filter_metadata=None)
            
        return [r.document.metadata.get("table", "") for r in results]

    def search_samples(
        self,
        query: str,
        top_k: int = 7,
        workspace: str | None = None,
    ) -> list[SQLSample]:
        """Return golden SQL samples ranked by similarity to *query*."""
        q_emb = self._embedder.embed(query)
        filter_ = {"workspace": workspace} if workspace else None
        results = self._sample_store.search(q_emb, top_k=top_k, filter_metadata=filter_)
        if not results and filter_ is not None:
            # Fallback: if strict workspace filter yields 0, search everywhere
            results = self._sample_store.search(q_emb, top_k=top_k, filter_metadata=None)

        samples = []
        for r in results:
            meta = r.document.metadata
            samples.append(
                SQLSample(
                    question=r.document.content,
                    sql=meta.get("sql", ""),
                    tables_used=meta.get("tables", "").split(","),
                    workspace=meta.get("workspace"),
                    description=meta.get("description"),
                )
            )
        return samples