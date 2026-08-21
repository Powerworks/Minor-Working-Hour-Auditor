"""
Verification script for ClickHouse MCP connection and run_select_query tool.

Tests:
1. Direct tool invocation of `run_select_query`.
2. Async MCP Server tool dispatch.
3. Verification that non-SELECT/mutation statements are strictly blocked.
4. Correct output structure: {"columns": [...], "rows": [[...], ...]}.
"""

import asyncio
import json
from mcp_server import execute_select_query, run_select_query, server


async def test_mcp_server():
    print("==================================================")
    print("🔍 Testing ClickHouse MCP Server & run_select_query")
    print("==================================================")

    # 1. Test MCP Tool Registration
    print("\n1. Verifying MCP Registered Tools:")
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    print(f"   Registered Tools: {tool_names}")
    assert "run_select_query" in tool_names, "run_select_query is not registered!"
    print("   ✓ run_select_query is properly registered.")

    # 2. Test query on labor_law_rules
    print("\n2. Executing run_select_query('SELECT state, min_age, max_age, school_day, max_work_hours_per_day, latest_end_time, source_citation FROM labor_law_rules ORDER BY min_age'):")
    sql_rules = "SELECT state, min_age, max_age, school_day, max_work_hours_per_day, latest_end_time, source_citation FROM labor_law_rules ORDER BY min_age"
    res_rules = run_select_query(sql_rules)
    print(f"   Columns ({len(res_rules['columns'])}): {res_rules['columns']}")
    print(f"   Rows returned: {len(res_rules['rows'])}")
    for row in res_rules["rows"]:
        print(f"     - State: {row[0]}, Age Band: [{row[1]}-{row[2]}], SchoolDay: {row[3]}, MaxWork: {row[4]}h, LatestEnd: {row[5]}")
        print(f"       Citation: {row[6][:80]}...")
    assert len(res_rules["rows"]) > 0, "Expected labor_law_rules to contain rows!"
    print("   ✓ labor_law_rules query verified.")

    # 3. Test query on cast_members & daily_schedule join
    print("\n3. Executing join query across cast_members and daily_schedule:")
    sql_join = """
    SELECT 
        c.cast_id, 
        c.name, 
        c.date_of_birth, 
        c.role, 
        s.scene_number, 
        s.start_time, 
        s.end_time
    FROM cast_members AS c
    LEFT JOIN daily_schedule AS s ON c.cast_id = s.cast_id
    ORDER BY c.cast_id
    """
    res_join = run_select_query(sql_join)
    print(f"   Columns ({len(res_join['columns'])}): {res_join['columns']}")
    print(f"   Rows returned: {len(res_join['rows'])}")
    for row in res_join["rows"]:
        print(f"     - {row[0]} | {row[1]} (DOB: {row[2]}) | Role: {row[3]} | Scene: {row[4]} ({row[5]} to {row[6]})")
    assert len(res_join["rows"]) > 0, "Expected join results!"
    print("   ✓ Cast & Schedule query verified.")

    # 4. Test async MCP tool dispatch
    print("\n4. Testing MCP server.call_tool('run_select_query', {'sql': 'SELECT count() as rule_count FROM labor_law_rules'}):")
    mcp_call_res = await server.call_tool("run_select_query", {"sql": "SELECT count() as rule_count FROM labor_law_rules"})
    print(f"   MCP Response: {mcp_call_res}")
    print("   ✓ MCP tool invocation via MCP Server protocol verified.")

    # 5. Security & Read-Only Enforcement Test
    print("\n5. Testing Read-Only Enforcement (Blocking DDL/DML):")
    forbidden_queries = [
        "DROP TABLE cast_members",
        "INSERT INTO cast_members VALUES ('fake', 'fake', 'fake', '2000-01-01', 'CA', 'fake')",
        "ALTER TABLE cast_members DELETE WHERE 1=1",
        "TRUNCATE TABLE labor_law_rules",
    ]
    for bad_sql in forbidden_queries:
        try:
            run_select_query(bad_sql)
            raise AssertionError(f"Security check failed! Mutation query was NOT blocked: {bad_sql}")
        except ValueError as err:
            print(f"   ✓ Blocked '{bad_sql[:25]}...': {err}")

    print("\n==================================================")
    print("🎉 ALL MCP CLICKHOUSE CONNECTION TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(test_mcp_server())
