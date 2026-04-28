"""
KeywordExtractor – Dynamically extracts keywords from PostgreSQL schema.

Handles:
- Snake_case/camelCase splitting
- Common DB prefixes/suffixes (tbl_, dim_, fact_, stg_, _v2, etc.)
- Domain keyword recognition from column names and types
- Description parsing

Single Responsibility: only extracts keywords from schema metadata.
No LLM, no embeddings – just text analysis.
"""
from __future__ import annotations

import re
import logging
from typing import Optional

from querygpt.models import TableSchema, ColumnInfo

logger = logging.getLogger(__name__)

# Common database prefixes to strip
DB_PREFIXES = {"tbl_", "dim_", "fact_", "stg_", "src_", "tmp_", "v_", "t_"}

# Common database suffixes to strip
DB_SUFFIXES = {"_v1", "_v2", "_v3", "_archive", "_old", "_new", "_temp"}

# Domain keyword mappings: column patterns → domain keywords
DOMAIN_KEYWORDS = {
    # Financial/Sales
    r"(price|cost|amount|revenue|total|invoice|payment|order|sale|transaction)": [
        "sales",
        "finance",
        "commerce",
    ],
    r"(discount|coupon|promotion|promo)": ["sales", "marketing"],
    r"(customer|client|account)": ["sales", "crm", "business"],

    # Users/Identity
    r"(user|account|profile|person|employee|admin|role|permission)": [
        "users",
        "identity",
        "access",
    ],
    r"(email|phone|address|contact)": ["users", "communication"],
    r"(login|password|auth|token|session)": ["identity", "security"],

    # Operations/Logistics
    r"(inventory|stock|warehouse|location|store|shelf|bin)": [
        "operations",
        "logistics",
    ],
    r"(shipment|delivery|order|fulfil|fulfill|tracking|package)": [
        "operations",
        "logistics",
    ],
    r"(supplier|vendor|procurement)": ["operations", "supply_chain"],

    # Time/Analytics
    r"(date|time|created|updated|timestamp|hour|day|week|month|year)": [
        "analytics",
        "temporal",
    ],
    r"(metric|kpi|funnel|conversion|report|dashboard|aggregat)": [
        "analytics",
        "reporting",
    ],

    # Product
    r"(product|item|catalog|sku|category|brand|description)": [
        "products",
        "inventory",
    ],

    # Communication
    r"(message|email|notification|sms|chat|comment|review)": [
        "communication",
        "engagement",
    ],

    # Geographic
    r"(country|city|state|region|zone|postal|zip|location|geo)": [
        "geographic",
        "location",
    ],
}

# Conversions: data_type patterns → domain hints
DATATYPE_KEYWORDS = {
    r"uuid": ["identity", "users"],
    r"json|jsonb": ["data", "analytics"],
    r"array": ["data", "collections"],
    r"enum": ["classification", "status"],
    r"boolean|bool": ["flag", "status"],
    r"decimal|numeric|money": ["finance", "commerce"],
    r"timestamp|date|time": ["temporal", "time"],
}


def _split_snake_case(name: str) -> list[str]:
    """
    Split snake_case or camelCase into words.

    Examples:
        customer_orders → ["customer", "orders"]
        customerOrders → ["customer", "orders"]
        OrderID → ["order", "id"]
    """
    # Replace underscores with spaces, then split on case changes
    name = name.replace("_", " ")
    # Insert space before uppercase letters (for camelCase)
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    # Split and filter
    words = [w.lower() for w in name.split() if w]
    return words


def _remove_prefixes_suffixes(words: list[str]) -> list[str]:
    """Remove common database prefixes and suffixes."""
    if not words:
        return words

    # Check first word for prefix
    first = words[0]
    if any(first.startswith(p.rstrip("_")) for p in DB_PREFIXES):
        words = words[1:] if len(words) > 1 else words

    if not words:
        return words

    # Check last word for suffix
    last = words[-1]
    for suffix in DB_SUFFIXES:
        if last.endswith(suffix.lstrip("_")):
            # Remove suffix
            words[-1] = last[: -len(suffix) + 1]
            if not words[-1]:  # If word becomes empty, remove it
                words = words[:-1]
            break

    return [w for w in words if w]  # Filter empty strings


def _extract_from_table_name(table_name: str) -> list[str]:
    """Extract keywords from table name."""
    words = _split_snake_case(table_name)
    words = _remove_prefixes_suffixes(words)
    return words


def _extract_from_columns(columns: list[ColumnInfo]) -> list[str]:
    """Extract keywords from column names and types."""
    keywords = set()

    for col in columns:
        # Parse column name
        words = _split_snake_case(col.name)
        keywords.update(words)

        # Parse data type
        data_type_lower = col.data_type.lower()
        for pattern, domain_kws in DATATYPE_KEYWORDS.items():
            if re.search(pattern, data_type_lower):
                keywords.update(domain_kws)

    return list(keywords)


def _extract_from_description(description: str) -> list[str]:
    """Extract keywords from table description (if available)."""
    if not description:
        return []

    # Simple word extraction from description
    words = re.findall(r"\b[a-z]{3,}\b", description.lower())
    # Filter common stop words
    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "from",
        "this",
        "are",
        "was",
        "been",
        "have",
        "has",
    }
    return [w for w in words if w not in stop_words]


def _match_domain_keywords(
    table_name: str, columns: list[ColumnInfo], description: str
) -> list[str]:
    """
    Match domain keywords based on table/column names and description.
    Returns workspace suggestions like ["sales", "users", "analytics"].
    """
    all_text = f"{table_name} {description} {' '.join(c.name for c in columns)}"
    all_text_lower = all_text.lower()

    matched_domains = set()

    for pattern, domains in DOMAIN_KEYWORDS.items():
        if re.search(pattern, all_text_lower):
            matched_domains.update(domains)

    return list(matched_domains)


def extract_keywords(
    table: TableSchema,
) -> dict[str, list[str]]:
    """
    Extract keywords from a table schema.

    Returns:
        {
            "table_keywords": ["customer", "order", ...],
            "domain_keywords": ["sales", "commerce", ...],
            "suggested_workspaces": ["sales", "commerce"],
        }
    """
    table_keywords = _extract_from_table_name(table.table_name)
    column_keywords = _extract_from_columns(table.columns)
    desc_keywords = _extract_from_description(table.description)

    # Combine all extracted keywords
    all_keywords = set(table_keywords + column_keywords + desc_keywords)

    # Match to domain workspaces
    domain_keywords = _match_domain_keywords(
        table.table_name, table.columns, table.description
    )

    logger.debug(
        "Extracted keywords for %s: table=%s, domain=%s",
        table.full_name,
        all_keywords,
        domain_keywords,
    )

    return {
        "table_keywords": sorted(all_keywords),
        "domain_keywords": sorted(set(domain_keywords)),
        "suggested_workspaces": sorted(set(domain_keywords)) or ["general"],
    }


def extract_keywords_batch(tables: list[TableSchema]) -> dict[str, dict]:
    """
    Extract keywords from multiple tables.

    Returns:
        {
            "public.orders": {"table_keywords": [...], "domain_keywords": [...]},
            "public.customers": {...},
            ...
        }
    """
    result = {}
    for table in tables:
        result[table.full_name] = extract_keywords(table)
    return result
