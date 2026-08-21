"""
Database setup script for Minor Working-Hour Auditor.

Applies `schema.sql` and `seed_data_CA.sql` to ClickHouse database.
Supports optional --clean / --reset flag to drop/recreate tables idempotently.
"""

import argparse
import os
from pathlib import Path
import clickhouse_connect
from dotenv import load_dotenv

load_dotenv()

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "default")
CLICKHOUSE_SECURE = os.getenv("CLICKHOUSE_SECURE", "false").lower() in ("true", "1", "yes")


def split_sql_statements(sql: str) -> list[str]:
    """
    Split SQL script into individual executable statements, respecting
    quoted string literals and SQL comments (so semicolons inside strings
    are not treated as statement terminators).
    """
    statements = []
    current = []
    in_single_quote = False
    in_line_comment = False
    in_block_comment = False
    i = 0
    n = len(sql)

    while i < n:
        c = sql[i]
        next_c = sql[i + 1] if i + 1 < n else ""

        if in_line_comment:
            if c == "\n":
                in_line_comment = False
            i += 1
            continue
        elif in_block_comment:
            if c == "*" and next_c == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        elif in_single_quote:
            current.append(c)
            if c == "\\":  # escape
                if i + 1 < n:
                    current.append(sql[i + 1])
                    i += 2
                    continue
            elif c == "'":
                if next_c == "'":  # escaped single quote ''
                    current.append(next_c)
                    i += 2
                    continue
                else:
                    in_single_quote = False
            i += 1
            continue
        else:
            if c == "-" and next_c == "-":
                in_line_comment = True
                i += 2
                continue
            elif c == "/" and next_c == "*":
                in_block_comment = True
                i += 2
                continue
            elif c == "'":
                in_quote = True
                in_single_quote = True
                current.append(c)
                i += 1
                continue
            elif c == ";":
                stmt = "".join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
                i += 1
                continue
            else:
                current.append(c)
                i += 1
                continue

    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)
    return statements


def main():
    parser = argparse.ArgumentParser(description="Setup ClickHouse database for Minor Working-Hour Auditor.")
    parser.add_argument("--clean", action="store_true", help="Drop existing tables before running schema and seeds.")
    args = parser.parse_args()

    print(f"Connecting to ClickHouse at {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT} (DB: {CLICKHOUSE_DATABASE})...")
    client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE,
        secure=CLICKHOUSE_SECURE,
    )

    tables = ["cast_members", "daily_schedule", "labor_law_rules"]

    if args.clean:
        print("\n[0/2] Dropping existing tables for clean setup...")
        for table in tables:
            client.command(f"DROP TABLE IF EXISTS {table}")
            print(f"  • Dropped {table} (if existed)")

    base_dir = Path(__file__).parent
    schema_path = base_dir / "schema.sql"
    seed_path = base_dir / "seed_data_CA.sql"

    print(f"\n[1/2] Applying schema and demo seeds from {schema_path.name}...")
    schema_sql = schema_path.read_text(encoding="utf-8")
    for stmt in split_sql_statements(schema_sql):
        client.command(stmt)
    print("✓ Schema and base seeds applied successfully.")

    print(f"\n[2/2] Applying California labor law seed data from {seed_path.name}...")
    seed_sql = seed_path.read_text(encoding="utf-8")
    for stmt in split_sql_statements(seed_sql):
        client.command(stmt)
    print("✓ California labor law seed data applied successfully.")

    print("\n--- Verifying Tables & Counts ---")
    for table in tables:
        count_res = client.query(f"SELECT count() FROM {table}")
        count = count_res.result_rows[0][0]
        print(f"  • {table}: {count} rows")

    client.close()
    print("\n✓ Database setup complete!")


if __name__ == "__main__":
    main()
