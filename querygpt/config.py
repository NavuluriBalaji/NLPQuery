"""
Centralised configuration loaded from environment variables.
Single Responsibility: only owns config, no logic.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class DatabaseConfig:
    host: str = os.getenv("DB_HOST", "localhost")
    port: int = int(os.getenv("DB_PORT", "5432"))
    name: str = os.getenv("DB_NAME", "querygpt")
    user: str = os.getenv("DB_USER", "postgres")
    password: str = os.getenv("DB_PASSWORD", "")
    pool_min: int = int(os.getenv("DB_POOL_MIN", "1"))
    pool_max: int = int(os.getenv("DB_POOL_MAX", "10"))


@dataclass(frozen=True)
class LLMConfig:
    provider: str = os.getenv("LLM_PROVIDER", "anthropic")   # "anthropic" | "openai" | "lmstudio" | "ollama"
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    model_anthropic: str = os.getenv("LLM_MODEL_ANTHROPIC", "claude-3-5-haiku-20241022")
    model_openai: str = os.getenv("LLM_MODEL_OPENAI", "gpt-4o-mini")
    model_lmstudio: str = os.getenv("LLM_MODEL_LMSTUDIO", "local-model")
    model_ollama: str = os.getenv("LLM_MODEL_OLLAMA", "llama3")
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str = os.getenv("EMBEDDING_PROVIDER", "openai")  # "openai" | "local"
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    dimension: int = int(os.getenv("EMBEDDING_DIM", "1536"))


@dataclass(frozen=True)
class VectorStoreConfig:
    backend: str = os.getenv("VECTOR_STORE", "pgvector")   # "pgvector" | "memory"
    top_k_schemas: int = int(os.getenv("VS_TOP_K_SCHEMAS", "5"))
    top_k_samples: int = int(os.getenv("VS_TOP_K_SAMPLES", "7"))


@dataclass(frozen=True)
class AppConfig:
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    vector_store: VectorStoreConfig = field(default_factory=VectorStoreConfig)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    custom_instructions: str = os.getenv("CUSTOM_INSTRUCTIONS", "")


# Singleton – import this everywhere
config = AppConfig()