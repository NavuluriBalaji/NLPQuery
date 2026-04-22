"""
Table Agent     – picks the best tables from candidates.
ColumnPruneAgent– strips irrelevant columns to reduce token usage.
SQLGeneratorAgent – final SQL generation with few-shot RAG context.
"""
from __future__ import annotations

import json
import logging
import re

from querygpt.agents.base import Agent
from querygpt.llm.base import LLMProvider
from querygpt.models import (
    AgentStatus,
    ColumnPruneAgentInput,
    ColumnPruneAgentOutput,
    SQLGeneratorInput,
    SQLGeneratorOutput,
    TableAgentInput,
    TableAgentOutput,
    TableSchema,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# TableAgent
# ===========================================================================

_TABLE_SYSTEM = """\
You are a database expert. Given a user question and a list of table schemas,
select the tables that are NECESSARY to answer the question.

Rules:
- Only include tables whose columns are actually needed.
- Prefer fewer tables unless a join is genuinely required.
- Return ONLY valid JSON, no markdown, no preamble.

Response format:
{
  "selected_tables": ["schema.table_a", "schema.table_b"],
  "reasoning": "..."
}
"""


class TableAgent(Agent[TableAgentInput, TableAgentOutput]):
    """
    SRP  : decides which tables are needed, nothing else.
    DIP  : depends on LLMProvider, not a concrete SDK.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def run(self, input_: TableAgentInput) -> TableAgentOutput:
        schemas_block = "\n\n".join(t.to_ddl() for t in input_.candidate_tables)

        user_msg = f"""\
Question: {input_.enhanced_question}

Available table schemas:
{schemas_block}

Select the required tables. Return JSON.
"""
        try:
            raw = self._llm.system_user(_TABLE_SYSTEM, user_msg, response_format="json")
            data = json.loads(raw)
            selected_names: list[str] = data.get("selected_tables", [])

            # map names back to TableSchema objects
            name_to_schema = {t.full_name: t for t in input_.candidate_tables}
            selected = [
                name_to_schema[n]
                for n in selected_names
                if n in name_to_schema
            ]

            # fallback: return all candidates if LLM gave nonsense
            if not selected:
                selected = input_.candidate_tables[: input_.top_k]

            return TableAgentOutput(
                status=AgentStatus.SUCCESS,
                selected_tables=selected,
                reasoning=data.get("reasoning"),
            )
        except Exception as exc:
            logger.warning("TableAgent failed (%s). Using all candidates.", exc)
            return TableAgentOutput(
                status=AgentStatus.ERROR,
                selected_tables=input_.candidate_tables[: input_.top_k],
                reasoning=str(exc),
            )


# ===========================================================================
# ColumnPruneAgent
# ===========================================================================

_PRUNE_SYSTEM = """\
You are a database schema optimizer. Given a user question and table schemas,
return a pruned version of each schema containing ONLY the columns needed to
answer the question.

Always keep:
- Primary key columns (even if not directly referenced).
- Foreign key columns used for joins.
- Columns explicitly or implicitly referenced in the question.

Return ONLY valid JSON, no markdown, no explanations outside JSON.

Response format:
{
  "pruned_schemas": {
    "schema.table_name": ["col1", "col2", ...],
    ...
  },
  "reasoning": "..."
}
"""


class ColumnPruneAgent(Agent[ColumnPruneAgentInput, ColumnPruneAgentOutput]):
    """
    SRP: removes irrelevant columns to shrink token usage.
    OCP: swap in a cheaper model here without touching other agents.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def run(self, input_: ColumnPruneAgentInput) -> ColumnPruneAgentOutput:
        schemas_block = "\n\n".join(t.to_ddl() for t in input_.selected_tables)

        user_msg = f"""\
Question: {input_.enhanced_question}

Table schemas to prune:
{schemas_block}

Return only the columns needed. Return JSON.
"""
        try:
            raw = self._llm.system_user(_PRUNE_SYSTEM, user_msg, response_format="json")
            data = json.loads(raw)
            pruned_map: dict[str, list[str]] = data.get("pruned_schemas", {})

            pruned_tables = []
            for table in input_.selected_tables:
                cols_to_keep = pruned_map.get(table.full_name)
                if cols_to_keep:
                    pruned_tables.append(table.prune_columns(cols_to_keep))
                else:
                    pruned_tables.append(table)  # keep original if not in response

            return ColumnPruneAgentOutput(
                status=AgentStatus.SUCCESS,
                pruned_tables=pruned_tables,
                reasoning=data.get("reasoning"),
            )
        except Exception as exc:
            logger.warning("ColumnPruneAgent failed (%s). Using full schemas.", exc)
            return ColumnPruneAgentOutput(
                status=AgentStatus.ERROR,
                pruned_tables=input_.selected_tables,
                reasoning=str(exc),
            )


# ===========================================================================
# SQLGeneratorAgent
# ===========================================================================

_SQL_SYSTEM = """\
You are an expert SQL engineer. Generate a correct, efficient SQL query that
answers the user's question using the provided table schemas and example queries.

Rules:
- Use ONLY columns that exist in the provided schemas.
- Prefer explicit JOINs over implicit comma joins.
- Always alias tables for readability.
- Add meaningful column aliases in SELECT.
- If filtering by date, use standard SQL date functions.
- Do NOT invent table or column names.
- Return ONLY valid JSON, no markdown, no backticks.

Response format:
{
  "sql": "SELECT ...",
  "explanation": "Step-by-step reasoning ..."
}
"""


class SQLGeneratorAgent(Agent[SQLGeneratorInput, SQLGeneratorOutput]):
    """
    SRP : only generates SQL from schemas + few-shot examples.
    DIP : LLMProvider is injected; no hardcoded SDK call.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def run(self, input_: SQLGeneratorInput) -> SQLGeneratorOutput:
        schemas_block = "\n\n".join(t.to_ddl() for t in input_.pruned_tables)

        samples_block = ""
        for s in input_.sql_samples:
            samples_block += f"-- Question: {s.question}\n{s.sql}\n\n"

        custom = (
            f"\nAdditional instructions:\n{input_.custom_instructions}\n"
            if input_.custom_instructions
            else ""
        )

        user_msg = f"""\
{custom}
Table schemas:
{schemas_block}

Example queries for reference:
{samples_block}

User question: {input_.enhanced_question}

Generate the SQL query. Return JSON.
"""
        try:
            raw = self._llm.system_user(_SQL_SYSTEM, user_msg, response_format="json")
            data = json.loads(raw)

            sql = data.get("sql", "").strip()
            # Strip accidental markdown fences
            sql = re.sub(r"```sql|```", "", sql).strip()

            return SQLGeneratorOutput(
                status=AgentStatus.SUCCESS,
                sql=sql,
                explanation=data.get("explanation"),
            )
        except Exception as exc:
            logger.error("SQLGeneratorAgent failed: %s", exc)
            return SQLGeneratorOutput(
                status=AgentStatus.ERROR,
                sql=None,
                explanation=None,
                error=str(exc),
            )