import logging
from querygpt.agents.intent import IntentAgent
from querygpt.agents.sql import TableAgent, ColumnPruneAgent, SQLGeneratorAgent
from querygpt.agents.base import RAGIndex
from querygpt.manager import WorkspaceManager
from querygpt.models import (
    QueryGPTRequest, QueryGPTResponse,
    IntentAgentInput, TableAgentInput, ColumnPruneAgentInput, SQLGeneratorInput,
    TableSchema, SQLSample
)

logger = logging.getLogger(__name__)

class QueryGPTPipeline:
    def __init__(
        self,
        intent_agent: IntentAgent,
        table_agent: TableAgent,
        prune_agent: ColumnPruneAgent,
        sql_agent: SQLGeneratorAgent,
        rag_index: RAGIndex,
        workspace_manager: WorkspaceManager,
        custom_instructions: str = ""
    ):
        self.intent_agent = intent_agent
        self.table_agent = table_agent
        self.prune_agent = prune_agent
        self.sql_agent = sql_agent
        self.rag_index = rag_index
        self.workspace_manager = workspace_manager
        self.custom_instructions = custom_instructions
        self._table_cache: dict[str, TableSchema] = {}

    def index_tables_batch(self, tables: list[TableSchema], workspace: str | None = None):
        self.rag_index.index_schemas_batch(tables, workspace)
        for t in tables:
            self._table_cache[t.full_name] = t

    def index_samples_batch(self, samples: list[SQLSample]):
        self.rag_index.index_samples_batch(samples)

    def run(self, req: QueryGPTRequest) -> QueryGPTResponse:
        # 1. Intent Phase
        intent_in = IntentAgentInput(
            user_question=req.question,
            available_workspaces=self.workspace_manager.list_names()
        )
        intent_out = self.intent_agent.run(intent_in)
        
        enhanced_q = intent_out.enhanced_question
        matched_ws = intent_out.matched_workspaces
        
        workspace_to_search = matched_ws[0] if matched_ws else req.workspace_hint

        # 2. RAG - Find candidate tables
        candidate_names = self.rag_index.search_schemas(
            query=enhanced_q,
            top_k=5,
            workspace=workspace_to_search
        )
        
        candidate_tables = [self._table_cache[n] for n in candidate_names if n in self._table_cache]

        if not candidate_tables:
            return QueryGPTResponse(
                question=req.question,
                enhanced_question=enhanced_q,
                matched_workspaces=matched_ws,
                error="No relevant tables found in the workspace."
            )

        # 3. Table Agent
        table_in = TableAgentInput(enhanced_question=enhanced_q, candidate_tables=candidate_tables)
        table_out = self.table_agent.run(table_in)
        
        # 4. Prune Agent
        prune_in = ColumnPruneAgentInput(enhanced_question=enhanced_q, selected_tables=table_out.selected_tables)
        prune_out = self.prune_agent.run(prune_in)

        # 5. RAG - SQL Samples
        samples = self.rag_index.search_samples(enhanced_q, top_k=3, workspace=workspace_to_search)

        # 6. SQL Generator
        sql_in = SQLGeneratorInput(
            enhanced_question=enhanced_q,
            pruned_tables=prune_out.pruned_tables,
            sql_samples=samples,
            custom_instructions=self.custom_instructions
        )
        sql_out = self.sql_agent.run(sql_in)

        return QueryGPTResponse(
            question=req.question,
            enhanced_question=enhanced_q,
            matched_workspaces=matched_ws,
            selected_tables=[t.full_name for t in table_out.selected_tables],
            generated_sql=sql_out.sql,
            explanation=sql_out.explanation,
            error=sql_out.error
        )