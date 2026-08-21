# 🎬 Minor Working-Hour Auditor

An autonomous AI agent built for the Google Cloud **Agentic Cinema Hackathon**. 

This tool acts as a legal compliance co-pilot for film production managers. It ingests natural language schedule changes, queries a ClickHouse database of cast data and state labor laws via the Model Context Protocol (MCP), and actively flags schedule changes that violate child labor regulations.

## 🏗️ Architecture
*   **LLM Engine:** Google Gemini 2.5 Flash (`google-genai` Python SDK)
*   **Integration Layer:** `@clickhouse/mcp-server` via standard I/O
*   **Database:** ClickHouse
*   **Frontend:** Streamlit

## ⚙️ How it Works
1. User inputs a schedule adjustment (e.g., *"Push Scene 12 by two hours"*).
2. Gemini receives the prompt under a strict "Lead Legal Compliance Auditor" system instruction.
3. The agent formulates a dynamic, read-only SQL query and calls the ClickHouse MCP server tool.
4. The MCP server executes the query and returns the relevant cast ages and state labor laws.
5. Gemini calculates the compliance deltas and outputs a structured Audit Report.

## 🚀 Setup Instructions
*(To be populated as development progresses)*

