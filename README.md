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

### 1. Prerequisites & Installation

Ensure you have Python 3.10+ installed. Install the required dependencies:

```bash
pip install -r requirements.txt
```

### 2. Start or Connect to ClickHouse

#### Option A: Local Docker Container (Recommended for development)
Run a local ClickHouse server container:

```bash
docker run -d \
  --name clickhouse-server \
  -p 8123:8123 \
  -p 9000:9000 \
  clickhouse/clickhouse-server:latest
```

#### Option B: ClickHouse Cloud
Create an instance on [ClickHouse Cloud](https://clickhouse.cloud) and obtain your hostname, port (typically `8443`), and credentials.

### 3. Environment Configuration

Copy the example environment file and configure your ClickHouse credentials:

```bash
cp .env.example .env
```

Edit `.env` as appropriate:
```env
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DATABASE=default
CLICKHOUSE_SECURE=false
```

### 4. Initialize Schema & Seed Data

Run the database setup script to apply `schema.sql` (table definitions and demo cast schedules) and `seed_data_CA.sql` (California labor law rules):

```bash
python setup_db.py
```

This creates the tables (`cast_members`, `daily_schedule`, `labor_law_rules`) and populates them with California child labor regulations and demo cast schedules.

### 5. Verify ClickHouse MCP Connection

Run the verification test script to confirm that the MCP server, read-only guardrails, and `run_select_query` tool operate correctly:

```bash
python verify_mcp.py
```

You can also launch the MCP server over standard I/O for client connections:

```bash
python mcp_server.py
```

#### MCP Tool Signature
* `run_select_query(sql: string) -> { columns: string[], rows: any[][] }`
* **Read-only enforcement**: Only `SELECT`, `WITH`, `SHOW`, `DESCRIBE`, `EXPLAIN`, and `EXISTS` statements are allowed; all DDL/DML mutations are strictly blocked.
