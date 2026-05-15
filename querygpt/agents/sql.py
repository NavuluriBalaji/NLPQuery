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
            data = json.loads(self._extract_json(raw), strict=False)
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
return a pruned version of each schema removing ONLY completely irrelevant columns.

Always keep:
- Primary key columns.
- Foreign key columns used for joins.
- Columns explicitly or implicitly referenced in the question.
- All identity/searchable columns like name, first_name, last_name, email, username, phone, status, type, role.
- Columns related to dates/times if the question could involve timing (created_at, updated_at, login_at, etc.).

Be CONSERVATIVE. When in doubt, keep the column.
Only remove columns that are clearly irrelevant (e.g., internal audit fields like `updated_by_ip`, `raw_payload`, `blob_data`).

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
            data = json.loads(self._extract_json(raw), strict=False)
            pruned_map: dict[str, list[str]] = data.get("pruned_schemas", {})

            pruned_tables = []
            MIN_COLUMNS = 5  # Safety floor: always keep at least 5 columns
            for table in input_.selected_tables:
                # Be flexible: check for "schema.table" OR just "table" in the LLM response
                cols_to_keep = pruned_map.get(table.full_name) or pruned_map.get(table.table_name)
                
                original_count = len(table.columns)
                if cols_to_keep:
                    pruned = table.prune_columns(cols_to_keep)
                    # Safety: if pruning went too aggressive, fall back to original
                    if len(pruned.columns) < MIN_COLUMNS and original_count > MIN_COLUMNS:
                        logger.warning(
                            "Pruning for %s was too aggressive (%d cols). Reverting to full schema.",
                            table.full_name, len(pruned.columns)
                        )
                        pruned_tables.append(table)
                    else:
                        pruned_tables.append(pruned)
                        logger.info(
                            "Pruned table %s: %d -> %d columns",
                            table.full_name, original_count, len(pruned.columns),
                        )
                else:
                    pruned_tables.append(table)  # keep original if not in response
                    logger.info("Table %s not pruned (using all %d columns)", table.full_name, original_count)

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
You are an expert PostgreSQL SQL engineer. The target database is ALWAYS PostgreSQL.
Generate a correct, efficient SQL query that answers the user's question using the
provided table schemas and example queries.

Rules:
- Use ONLY columns that exist in the provided schemas.
- Creatively map user terms to the actual column names (e.g., if user asks for "username" but the table has "email" or "name", use those).
- Prefer explicit JOINs over implicit comma joins.
- Always alias tables for readability.
- Add meaningful column aliases in SELECT.
- If filtering by date, use standard PostgreSQL date functions (NOW(), CURRENT_DATE, etc.).
- Do NOT invent table or column names. Only if the request is truly impossible to answer with the provided columns, provide an error explaining what is missing.
- Return ONLY valid JSON, no markdown, no backticks.

POSTGRESQL-SPECIFIC RULES (CRITICAL):
- NEVER use MySQL-specific functions or columns. Specifically FORBIDDEN:
  - `information_schema.tables.TABLE_ROWS`  → use `pg_class.reltuples::bigint` instead
  - `GROUP_CONCAT()`                         → use `STRING_AGG()` instead
  - `IFNULL()`                               → use `COALESCE()` instead
  - `LIMIT x OFFSET y` with comma syntax    → always use `LIMIT x OFFSET y`
  - Backtick identifiers                     → use double-quotes e.g. "column_name"
- For row count estimates, use: `SELECT reltuples::bigint FROM pg_class WHERE relname = 'table_name'`

Response format:
{
  "sql": "SELECT ...",
  "explanation": "Plain English explanation of what this SQL does, step-by-step, suitable for a non-technical user.",
  "follow_up_questions": ["Suggested follow-up question 1?", "Suggested follow-up question 2?", "Suggested follow-up question 3?"],
  "error": null
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
            data = json.loads(self._extract_json(raw), strict=False)

            sql = data.get("sql")
            if sql:
                sql = sql.strip()
                # Strip accidental markdown fences
                sql = re.sub(r"```sql|```", "", sql).strip()

            error_msg = data.get("error")

            return SQLGeneratorOutput(
                status=AgentStatus.ERROR if error_msg else AgentStatus.SUCCESS,
                sql=sql,
                explanation=data.get("explanation"),
                follow_up_questions=data.get("follow_up_questions", []),
                error=error_msg
            )

        except Exception as exc:
            logger.error("SQLGeneratorAgent failed: %s", exc)
            return SQLGeneratorOutput(
                status=AgentStatus.ERROR,
                sql=None,
                explanation=None,
                error=str(exc),
            )