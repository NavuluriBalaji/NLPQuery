from querygpt.config import AppConfig
from querygpt.pipeline import QueryGPTPipeline
from querygpt.llm.providers import build_llm_provider
from querygpt.embeddings.providers import build_embedding_provider
from querygpt.vector_store.store import build_vector_store
from querygpt.agents.intent import IntentAgent
from querygpt.agents.sql import TableAgent, ColumnPruneAgent, SQLGeneratorAgent
from querygpt.agents.base import RAGIndex
from querygpt.manager import WorkspaceManager

def build_pipeline(config: AppConfig) -> QueryGPTPipeline:
    # 1. Providers
    llm_kwargs = {}
    if config.llm.provider == "anthropic":
        llm_kwargs["api_key"] = config.llm.anthropic_api_key
        llm_kwargs["model"] = config.llm.model_anthropic
    elif config.llm.provider == "openai":
        llm_kwargs["api_key"] = config.llm.openai_api_key
        llm_kwargs["model"] = config.llm.model_openai
    elif config.llm.provider == "lmstudio":
        llm_kwargs["model"] = config.llm.model_lmstudio
    elif config.llm.provider == "ollama":
        llm_kwargs["model"] = config.llm.model_ollama

    llm = build_llm_provider(config.llm.provider, **llm_kwargs)
    
    emb_kwargs = {}
    if config.embedding.provider == "openai":
        emb_kwargs["api_key"] = config.embedding.openai_api_key
        emb_kwargs["model"] = config.embedding.model
        emb_kwargs["dim"] = config.embedding.dimension
    
    embedder = build_embedding_provider(config.embedding.provider, **emb_kwargs)

    # 2. Vector Stores
    vs_kwargs = {}
    if config.vector_store.backend == "pgvector":
        from querygpt.db.postgres import PostgresConnector
        connector = PostgresConnector(config.db)
        connector.connect()
        schema_store = build_vector_store("pgvector", connector=connector, dimension=embedder.dimension, table_name="schemas")
        sample_store = build_vector_store("pgvector", connector=connector, dimension=embedder.dimension, table_name="samples")
    else:
        schema_store = build_vector_store("memory")
        sample_store = build_vector_store("memory")

    rag_index = RAGIndex(schema_store, sample_store, embedder)

    # 3. Agents
    intent_agent = IntentAgent(llm)
    table_agent = TableAgent(llm)
    prune_agent = ColumnPruneAgent(llm)
    sql_agent = SQLGeneratorAgent(llm)

    workspace_manager = WorkspaceManager()

    # 4. Pipeline
    return QueryGPTPipeline(
        intent_agent=intent_agent,
        table_agent=table_agent,
        prune_agent=prune_agent,
        sql_agent=sql_agent,
        rag_index=rag_index,
        workspace_manager=workspace_manager,
        custom_instructions=config.custom_instructions
    )