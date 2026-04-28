"""
SQL Validator – Restricts dangerous operations.

Prevents execution of:
- INSERT
- UPDATE
- DELETE
- TRUNCATE
- DROP
- ALTER
- CREATE

Single Responsibility: validates SQL for security.
"""
from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)

# Dangerous operations that should be blocked
BLOCKED_OPERATIONS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "DROP",
    "ALTER",
    "CREATE",
    "EXEC",
    "EXECUTE",
}

ALLOWED_OPERATIONS = {
    "SELECT",
    "WITH",  # CTEs with SELECT
}


def is_write_operation(sql: str) -> bool:
    """
    Check if SQL contains write operations (INSERT, UPDATE, DELETE, TRUNCATE, etc.).
    
    Returns:
        True if the SQL contains blocked operations, False otherwise.
    """
    if not sql:
        return False
    
    # Normalize: remove comments, whitespace, convert to uppercase
    sql_clean = _remove_comments(sql).strip().upper()
    
    # Split by semicolons to handle multiple statements
    statements = [s.strip() for s in sql_clean.split(";") if s.strip()]
    
    for stmt in statements:
        # Get first keyword
        first_keyword = _get_first_keyword(stmt)
        
        if first_keyword in BLOCKED_OPERATIONS:
            logger.warning(f"Blocked operation detected: {first_keyword}")
            return True
        
        # Check for dangerous keywords anywhere in the statement
        for op in BLOCKED_OPERATIONS:
            # Use word boundary to avoid matching substrings
            if re.search(rf"\b{op}\b", stmt):
                logger.warning(f"Blocked operation detected: {op}")
                return True
    
    return False


def _remove_comments(sql: str) -> str:
    """Remove SQL comments (-- and /* */)."""
    # Remove single-line comments (-- ...)
    sql = re.sub(r"--[^\n]*", "", sql)
    # Remove multi-line comments (/* ... */)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql


def _get_first_keyword(sql: str) -> str:
    """Extract the first keyword from SQL statement."""
    # Remove leading whitespace
    sql = sql.strip()
    # Match first word (sequence of alphanumeric + underscore)
    match = re.match(r"(\w+)", sql)
    return match.group(1).upper() if match else ""


def validate_sql(sql: str) -> tuple[bool, str | None]:
    """
    Validate SQL query for security.
    
    Args:
        sql: The SQL query to validate
        
    Returns:
        (is_valid, error_message)
        - is_valid: True if SQL is safe, False if it contains blocked operations
        - error_message: Human-readable error message if invalid, None if valid
    """
    if not sql or not sql.strip():
        return False, "SQL query is empty."
    
    if is_write_operation(sql):
        return False, (
            "❌ Write operations are not allowed. "
            "Only SELECT queries are permitted.\n\n"
            "Blocked operations: INSERT, UPDATE, DELETE, TRUNCATE, DROP, ALTER, CREATE, EXEC\n\n"
            "This is a read-only database interface for security reasons."
        )
    
    return True, None


def get_validation_prompt() -> str:
    """Return system prompt instruction about SQL restrictions."""
    return """\
IMPORTANT SECURITY CONSTRAINT:
You MUST ONLY generate SELECT queries. 
DO NOT generate INSERT, UPDATE, DELETE, TRUNCATE, DROP, ALTER, CREATE, or EXEC statements.
If the user asks for a write operation, you should:
1. Refuse to generate the query
2. Explain that only SELECT queries are allowed
3. Suggest a SELECT query that would show the same information instead

Examples of REJECTED queries:
- "INSERT INTO customers VALUES (...)" ❌
- "UPDATE orders SET status = 'shipped'" ❌
- "DELETE FROM users WHERE id = 1" ❌
- "TRUNCATE TABLE logs" ❌

Examples of ALLOWED queries:
- "SELECT * FROM customers" ✅
- "SELECT COUNT(*) FROM orders WHERE status = 'shipped'" ✅
- "WITH recent_orders AS (...) SELECT * FROM recent_orders" ✅
"""
