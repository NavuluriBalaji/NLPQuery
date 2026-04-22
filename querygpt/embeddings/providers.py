"""
Embedding providers.

Interface Segregation – EmbeddingProvider exposes only what vector search needs.
Open/Closed           – add SentenceTransformerProvider, CohereProvider, etc.
                        without touching the vector store or agents.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class EmbeddingProvider(ABC):
    """Contract: turn a string into a fixed-length float vector."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return embedding for a single piece of text."""

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Default: embed one-by-one. Override for batched efficiency."""
        return [self.embed(t) for t in texts]

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Size of output vectors."""


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""


# ---------------------------------------------------------------------------
# OpenAI implementation
# ---------------------------------------------------------------------------

class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Uses OpenAI text-embedding-3-* models."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dim: int = 1536,
    ) -> None:
        try:
            import openai as _openai
        except ImportError as exc:
            raise ImportError("pip install openai") from exc
        self._client = _openai.OpenAI(api_key=api_key)
        self._model = model
        self._dim = dim

    def embed(self, text: str) -> list[float]:
        try:
            resp = self._client.embeddings.create(input=[text], model=self._model)
            return resp.data[0].embedding
        except Exception as exc:
            raise EmbeddingError(str(exc)) from exc

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            resp = self._client.embeddings.create(input=texts, model=self._model)
            return [item.embedding for item in resp.data]
        except Exception as exc:
            raise EmbeddingError(str(exc)) from exc

    @property
    def dimension(self) -> int:
        return self._dim


# ---------------------------------------------------------------------------
# Local / sentence-transformers implementation (no API key needed)
# ---------------------------------------------------------------------------

class LocalEmbeddingProvider(EmbeddingProvider):
    """
    Uses sentence-transformers for fully local embeddings.
    pip install sentence-transformers
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError("pip install sentence-transformers") from exc
        self._model = SentenceTransformer(model_name)
        self._dim = self._model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> list[float]:
        return self._model.encode(text).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts).tolist()

    @property
    def dimension(self) -> int:
        return self._dim


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_embedding_provider(provider: str, **kwargs) -> EmbeddingProvider:
    registry: dict[str, type[EmbeddingProvider]] = {
        "openai": OpenAIEmbeddingProvider,
        "local":  LocalEmbeddingProvider,
    }
    cls = registry.get(provider.lower())
    if cls is None:
        raise ValueError(
            f"Unknown embedding provider '{provider}'. "
            f"Available: {list(registry.keys())}"
        )
    return cls(**kwargs)