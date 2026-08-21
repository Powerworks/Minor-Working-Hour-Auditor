"""
ClickHouse MCP Server for Minor Working-Hour Auditor.

Exposes a read-only Model Context Protocol (MCP) tool:
    run_select_query(sql: str) -> {"columns": list[str], "rows": list[list[any]]}
"""

import os
import re
import datetime
from decimal import Decimal
from typing import Any, Dict, List
import clickhouse_connect
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

# Load environment configuration
load_dotenv()

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "default")
CLICKHOUSE_SECURE = os.getenv("CLICKHOUSE_SECURE", "false").lower() in ("true", "1", "yes")

FORBIDDEN_SQL_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "REPLACE", "RENAME", "OPTIMIZE", "SYSTEM",
    "GRANT", "REVOKE", "ATTACH", "DETACH", "KILL"
)

ALLOWED_SQL_STARTS = ("SELECT", "WITH", "SHOW", "DESCRIBE", "DESC", "EXPLAIN", "EXISTS")


def get_clickhouse_client():
    """Create and return a ClickHouse connect client."""
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE,
        secure=CLICKHOUSE_SECURE,
        settings={"readonly": 1},
    )


def _serialize_value(val: Any) -> Any:
    """Convert ClickHouse values (dates, datetimes, decimals) to JSON-serializable types."""
    if val is None:
        return None
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    return val


def execute_select_query(sql: str) -> Dict[str, Any]:
    """
    Validate and execute a read-only query against ClickHouse.

    Args:
        sql: SQL query string (must be read-only).

    Returns:
        Dict with keys:
            - columns: list of column names
            - rows: list of row lists
    """
    # Clean SQL string and remove SQL comments
    clean_sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    clean_sql = re.sub(r"/\*.*?\*/", "", clean_sql, flags=re.DOTALL).strip()

    if not clean_sql:
        raise ValueError("Empty SQL query provided.")

    # Extract first token
    first_word_match = re.match(r"^[A-Za-z]+", clean_sql)
    first_word = first_word_match.group(0).upper() if first_word_match else ""

    if first_word not in ALLOWED_SQL_STARTS:
        raise ValueError(
            f"Only read-only queries are permitted. Query must start with one of {ALLOWED_SQL_STARTS}, got: '{first_word}'"
        )

    # Check for forbidden mutation keywords across statements
    sql_tokens = [tok.upper() for tok in re.findall(r"\b[A-Za-z_]+\b", clean_sql)]
    for forbidden in FORBIDDEN_SQL_KEYWORDS:
        if forbidden in sql_tokens:
            raise ValueError(f"Forbidden mutation keyword '{forbidden}' detected in query.")

    client = get_clickhouse_client()
    try:
        query_result = client.query(clean_sql)
        columns: List[str] = list(query_result.column_names)
        raw_rows = query_result.result_rows
        rows: List[List[Any]] = [
            [_serialize_value(val) for val in row]
            for row in raw_rows
        ]
        return {
            "columns": columns,
            "rows": rows,
        }
    finally:
        client.close()


# Initialize MCP Server
server = MCPServer("clickhouse-mcp")


@server.tool(
    name="run_select_query",
    description="Execute a read-only SELECT query against the ClickHouse database and return columns and rows.",
)
def run_select_query(sql: str) -> Dict[str, Any]:
    """
    Execute a read-only SELECT query against ClickHouse.

    Args:
        sql: The SELECT SQL query string to execute.

    Returns:
        A dictionary with 'columns' (list of string column names) and 'rows' (list of lists of cell values).
    """
    return execute_select_query(sql)


def main():
    """Run the MCP server via stdio transport."""
    import asyncio
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
