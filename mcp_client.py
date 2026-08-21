"""
MCP Client for interacting with the ClickHouse MCP Server over stdio.
Spawns `mcp_server.py` as a subprocess and provides a clean async/sync interface.
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class ClickHouseMCPClient:
    """Async & Sync wrapper around the ClickHouse MCP stdio server."""

    def __init__(self, server_script: str = "mcp_server.py"):
        self.server_script = os.path.abspath(server_script)
        self.query_log: List[Dict[str, Any]] = []

    def _get_server_params(self) -> StdioServerParameters:
        return StdioServerParameters(
            command=sys.executable,
            args=[self.server_script],
            env=os.environ.copy(),
        )

    async def execute_query(self, sql: str) -> Dict[str, Any]:
        """
        Execute a read-only SQL query against ClickHouse via the MCP server.

        Args:
            sql: Read-only SELECT query string.

        Returns:
            Dict containing 'columns' and 'rows', or 'error' if execution failed.
        """
        log_entry: Dict[str, Any] = {
            "sql": sql,
            "success": False,
            "result": None,
            "error": None,
        }

        try:
            params = self._get_server_params()
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    mcp_res = await session.call_tool("run_select_query", arguments={"sql": sql})

                    if mcp_res.is_error:
                        err_msg = ""
                        for item in mcp_res.content:
                            if getattr(item, "type", None) == "text":
                                err_msg += item.text
                        log_entry["error"] = err_msg or "MCP execution error"
                        self.query_log.append(log_entry)
                        return {"error": log_entry["error"], "columns": [], "rows": []}

                    # Parse output
                    res_data = None
                    for item in mcp_res.content:
                        if getattr(item, "type", None) == "text":
                            try:
                                res_data = json.loads(item.text)
                                break
                            except Exception:
                                res_data = {"raw": item.text}

                    if res_data is None:
                        res_data = {"columns": [], "rows": []}

                    log_entry["success"] = True
                    log_entry["result"] = res_data
                    self.query_log.append(log_entry)
                    return res_data

        except Exception as ex:
            log_entry["error"] = str(ex)
            self.query_log.append(log_entry)
            return {"error": str(ex), "columns": [], "rows": []}

    def execute_query_sync(self, sql: str) -> Dict[str, Any]:
        """Synchronous wrapper for execute_query."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(self.execute_query(sql))
            else:
                return asyncio.run(self.execute_query(sql))
        except RuntimeError:
            return asyncio.run(self.execute_query(sql))


if __name__ == "__main__":
    client = ClickHouseMCPClient()
    print("Testing ClickHouseMCPClient directly...")
    result = client.execute_query_sync("SELECT name, role FROM cast_members ORDER BY cast_id")
    print("Result:", json.dumps(result, indent=2))
