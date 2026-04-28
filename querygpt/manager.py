"""
WorkspaceManager

Manages domain workspaces: maps a workspace name to its table names and
golden SQL samples. Also bootstraps the system workspaces.

SRP : only knows about workspace configuration, not about LLMs or embeddings.
OCP : add new system workspaces in SYSTEM_WORKSPACES dict; no code changes needed.
"""
from __future__ import annotations

import logging
from typing import Optional

from querygpt.models import SQLSample, Workspace, WorkspaceType, TableSchema
from querygpt.keyword_extractor import extract_keywords

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Built-in system workspaces (analogous to Uber's "Mobility", "Ads", etc.)
# Adapt these to your domain.
# ---------------------------------------------------------------------------

SYSTEM_WORKSPACES: dict[str, dict] = {
    "general": {
        "description": "General purpose workspace for cross-domain queries.",
        "keywords": ["data", "record", "count", "list", "find"],
        "table_names": [],  # populated dynamically from all tables
    },
    "sales": {
        "description": "Orders, customers, revenue, and sales performance.",
        "keywords": ["order", "revenue", "sale", "customer", "purchase", "invoice"],
        "table_names": [],
    },
    "operations": {
        "description": "Logistics, inventory, fulfilment, and supply chain.",
        "keywords": ["inventory", "stock", "warehouse", "shipment", "fulfilment"],
        "table_names": [],
    },
    "users": {
        "description": "User accounts, authentication, profiles, and activity.",
        "keywords": ["user", "account", "login", "profile", "session", "signup"],
        "table_names": [],
    },
    "analytics": {
        "description": "Metrics, KPIs, funnels, and aggregated reporting.",
        "keywords": ["metric", "kpi", "funnel", "conversion", "report", "aggregate"],
        "table_names": [],
    },
}


class WorkspaceManager:
    """Stores and serves workspace configurations in memory."""

    def __init__(self) -> None:
        self._workspaces: dict[str, Workspace] = {}
        self._bootstrap_system_workspaces()

    def _bootstrap_system_workspaces(self) -> None:
        for name, cfg in SYSTEM_WORKSPACES.items():
            ws = Workspace(
                name=name,
                type=WorkspaceType.SYSTEM,
                description=cfg["description"],
                table_names=cfg.get("table_names", []),
                keywords=cfg.get("keywords", []),
            )
            self._workspaces[name] = ws
        logger.info("Bootstrapped %d system workspaces.", len(SYSTEM_WORKSPACES))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register(self, workspace: Workspace) -> None:
        """Register or update a workspace."""
        self._workspaces[workspace.name] = workspace
        logger.debug("Workspace registered: %s", workspace.name)

    def get(self, name: str) -> Optional[Workspace]:
        return self._workspaces.get(name)

    def list_names(self) -> list[str]:
        return list(self._workspaces.keys())

    def list_all(self) -> list[Workspace]:
        return list(self._workspaces.values())

    def add_table_to_workspace(self, workspace_name: str, table_full_name: str) -> None:
        ws = self._workspaces.get(workspace_name)
        if ws and table_full_name not in ws.table_names:
            updated = ws.model_copy(
                update={"table_names": ws.table_names + [table_full_name]}
            )
            self._workspaces[workspace_name] = updated

    def tables_for_workspace(self, workspace_name: str) -> list[str]:
        ws = self.get(workspace_name)
        return ws.table_names if ws else []

    def assign_tables_by_keyword(
        self, table_full_name: str, table: TableSchema | None = None, description: str = ""
    ) -> None:
        """
        Auto-assign a table to workspaces using dynamic keyword extraction.
        
        Args:
            table_full_name: The table's full name (schema.table)
            table: TableSchema object for dynamic keyword extraction (preferred)
            description: Legacy fallback if TableSchema not provided
            
        Called during schema indexing for zero-config workspace assignment.
        """
        # If TableSchema provided, use dynamic keyword extraction
        if table:
            extracted = extract_keywords(table)
            suggested_workspaces = extracted.get("suggested_workspaces", [])
            table_keywords = set(extracted.get("table_keywords", []))
            domain_keywords = set(extracted.get("domain_keywords", []))
            all_keywords = table_keywords | domain_keywords
        else:
            # Fallback to description-based matching (legacy)
            all_keywords = set(description.lower().split())
            suggested_workspaces = []

        # Assign to matching workspaces
        for ws in self._workspaces.values():
            ws_keywords = set(ws.keywords)
            
            # Match if:
            # 1. Workspace is in suggested_workspaces from keyword extractor, OR
            # 2. Any extracted keywords match workspace keywords
            if suggested_workspaces and ws.name in suggested_workspaces:
                self.add_table_to_workspace(ws.name, table_full_name)
                logger.debug(
                    "Assigned %s to workspace '%s' (suggested)",
                    table_full_name,
                    ws.name,
                )
            elif ws_keywords & all_keywords:  # Set intersection
                self.add_table_to_workspace(ws.name, table_full_name)
                logger.debug(
                    "Assigned %s to workspace '%s' (keyword match)",
                    table_full_name,
                    ws.name,
                )

    # ------------------------------------------------------------------
    # Lookup helpers used by the pipeline
    # ------------------------------------------------------------------

    def resolve_workspaces(self, names: list[str]) -> list[Workspace]:
        """Return Workspace objects for given names; skip unknowns."""
        return [self._workspaces[n] for n in names if n in self._workspaces]