from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

class AgentStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"

@dataclass
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool = True
    description: str | None = None
    is_primary_key: bool = False

@dataclass
class TableSchema:
    table_name: str
    schema_name: str
    description: str = ""
    columns: list[ColumnInfo] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.schema_name}.{self.table_name}"
    
    def to_ddl(self) -> str:
        cols = [f"{c.name} {c.data_type}" for c in self.columns]
        return f"CREATE TABLE {self.full_name} (\n  " + ",\n  ".join(cols) + "\n);"

    def prune_columns(self, cols_to_keep: list[str]) -> TableSchema:
        cols = [c for c in self.columns if c.name in cols_to_keep or c.is_primary_key]
        return TableSchema(
            table_name=self.table_name,
            schema_name=self.schema_name,
            description=self.description,
            columns=cols
        )

@dataclass
class SQLSample:
    question: str
    sql: str
    tables_used: list[str] = field(default_factory=list)
    workspace: str | None = None
    description: str | None = None

@dataclass
class QueryGPTRequest:
    question: str
    workspace_hint: str | None = None

@dataclass
class QueryGPTResponse:
    question: str
    enhanced_question: str | None = None
    matched_workspaces: list[str] = field(default_factory=list)
    selected_tables: list[str] = field(default_factory=list)
    generated_sql: str | None = None
    explanation: str | None = None
    error: str | None = None

@dataclass
class EmbeddedDocument:
    id: str
    content: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class SearchResult:
    document: EmbeddedDocument
    score: float

class WorkspaceType(Enum):
    SYSTEM = "system"
    CUSTOM = "custom"

@dataclass
class Workspace:
    name: str
    type: WorkspaceType = WorkspaceType.SYSTEM
    description: str = ""
    table_names: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

@dataclass
class IntentAgentInput:
    user_question: str
    available_workspaces: list[str]

@dataclass
class IntentAgentOutput:
    status: AgentStatus
    matched_workspaces: list[str]
    enhanced_question: str
    reasoning: str | None = None

@dataclass
class TableAgentInput:
    enhanced_question: str
    candidate_tables: list[TableSchema]
    top_k: int = 5

@dataclass
class TableAgentOutput:
    status: AgentStatus
    selected_tables: list[TableSchema]
    reasoning: str | None = None

@dataclass
class ColumnPruneAgentInput:
    enhanced_question: str
    selected_tables: list[TableSchema]

@dataclass
class ColumnPruneAgentOutput:
    status: AgentStatus
    pruned_tables: list[TableSchema]
    reasoning: str | None = None

@dataclass
class SQLGeneratorInput:
    enhanced_question: str
    pruned_tables: list[TableSchema]
    sql_samples: list[SQLSample]
    custom_instructions: str | None = None

@dataclass
class SQLGeneratorOutput:
    status: AgentStatus
    sql: str | None
    explanation: str | None = None
    error: str | None = None
