# 🎬 Minor Working-Hour Auditor

An autonomous AI agent built for the Google Cloud **Agentic Cinema Hackathon**. 

This tool acts as a legal compliance co-pilot for film production managers. It ingests natural language schedule changes, queries a ClickHouse database of cast data and state labor laws via the Model Context Protocol (MCP), and actively flags schedule changes that violate child labor regulations.

## 🏗️ Architecture
*   **LLM Engine:** Google Gemini 3.6 Flash (`google-genai` Python SDK)
*   **Integration Layer:** `@clickhouse/mcp-server` via standard I/O
*   **Database:** ClickHouse
*   **Frontend:** Streamlit

```mermaid
flowchart LR
    User["Production Manager"] -->|"NL schedule change\n(e.g. \"Push Scene 12 by two hours\")"| UI["Streamlit UI\napp.py"]
    UI --> Auditor["Gemini Compliance Auditor\nauditor.py\n(google-genai, Gemini 3.6 Flash)"]
    Auditor -->|"function call:\nrun_select_query(sql)"| MCPClient["MCP Client\nmcp_client.py"]
    MCPClient <-->|"stdio subprocess"| MCPServer["ClickHouse MCP Server\nmcp_server.py\n(read-only guardrails)"]
    MCPServer -->|"SELECT"| DB[("ClickHouse\ncast_members\ndaily_schedule\nlabor_law_rules")]
    DB -->|"columns + rows"| MCPServer
    MCPServer --> MCPClient
    MCPClient --> Auditor
    Auditor -->|"Audit Report JSON\n(compliant / violations /\nrule_confidence)"| UI
    UI -->|"pass banner, violation cards,\ncontested-interpretation badge"| User
```

The Gemini engine never reasons about labor law from its own training data — every rule, cap, and citation in the Audit Report is sourced from a queried `labor_law_rules` row via the MCP tool call above.

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

---

## 🖥️ Running the Streamlit App

### 1. Configure Gemini API Key

Add your Gemini API key to `.env` (or enter it in the Streamlit UI sidebar):

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2. Launch the Application

Start the Streamlit dashboard:

```bash
streamlit run app.py
```

The web interface will open at `http://localhost:8501`.

---

## 🎬 Demo Scenarios & Sample Inputs

Use these sample natural language schedule change descriptions to test the system during the demo video:

### 🟡 Scenario 1: The Contested 16–18 Band Showcase (Quality of Idea)
* **Prompt:** `Extend Kiernan Shipka's shoot on 2026-08-25 from 08:00-16:00 to 08:00-17:00 for Scene Sc_103.`
* **Cast Member:** Kiernan Shipka (`cast_003`, Age 16)
* **Statutory Conflict:** Triggers the statutory tension between **8 CCR §11760** (10-hour workplace presence allowance on school days) and **Cal. Labor Code §1308.7** (8-hour statutory cap).
* **Expected UI Payoff:** Visibly renders an amber alert badge with `"⚠️ Contested Interpretation — Unconfirmed by Counsel"` and a detailed legal explanation explaining the more-protective-governs canon.

### 🔴 Scenario 2: Daily Work Hours Overtime Violation
* **Prompt:** `Extend Maya Lin's shoot on 2026-08-25 from 09:00 to 15:00 for Scene Sc_101.`
* **Cast Member:** Maya Lin (`cast_001`, Age 6)
* **Statute:** 8 CCR §11760 (Max 4.0 work hours per day for ages 6–8 on school days).
* **Expected UI Payoff:** Flags a `CRITICAL` statutory violation (`max_daily_work_hours_exceeded` — 6.0h proposed vs 4.0h max allowed).

### 🔴 Scenario 3: Night Curfew Wrap Violation
* **Prompt:** `Reschedule Jacob Tremblay's call on 2026-08-25 to 15:00-23:00 for Scene Sc_102.`
* **Cast Member:** Jacob Tremblay (`cast_002`, Age 11)
* **Statute:** Cal. Labor Code §1308.7 & 8 CCR §11760 (Mandatory wrap by 22:00 on school nights).
* **Expected UI Payoff:** Flags a `CRITICAL` curfew violation (`late_wrap_curfew_violation` — wrapping at 23:00 past the 22:00 statutory limit).

### 🟢 Scenario 4: Fully Compliant Schedule Adjustment
* **Prompt:** `Adjust Maya Lin's call on 2026-08-25 to 09:30-13:00 (3.5 hours) for Scene Sc_101.`
* **Cast Member:** Maya Lin (`cast_001`, Age 6)
* **Expected UI Payoff:** Green status banner `✅ COMPLIANT — SCHEDULE CHANGE APPROVED` with zero violations.

---

## 🔒 Frozen Scope Compliance Note
* `mcp_server.py`, `schema.sql`, `seed_data_CA.sql`, `setup_db.py`, and `verify_mcp.py` are strictly maintained in their original frozen states.
* Compliance auditing logic is executed using `google-genai` with Gemini 3.6 Flash via standard I/O MCP calls to ClickHouse.

## 📄 License

MIT — see [LICENSE](./LICENSE).

