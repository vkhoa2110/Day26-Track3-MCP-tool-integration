# SQLite FastMCP Database Lab

This repository contains a complete implementation of the lab: a FastMCP server backed by SQLite with three tools, schema resources, validation, tests, and client setup examples.

## Project Layout

```text
implementation/
  db.py                 # SQLite adapter, validation, safe SQL builders
  init_db.py            # reproducible schema and seed data
  mcp_server.py         # FastMCP tools and resources
  verify_server.py      # protocol-level smoke test with fastmcp.Client
  requirements.txt
  start_inspector.ps1
  tests/
    test_db.py
    test_mcp_server.py
pseudocode/             # original lab starter pseudocode
```

## Setup

```powershell
cd D:\DSA\Day26-Track3-MCP-tool-integration
python -m pip install -r implementation\requirements.txt
python implementation\init_db.py --reset
```

The server also creates `implementation/lab.sqlite3` automatically on first start.

## Run The MCP Server

Default stdio transport:

```powershell
python implementation\mcp_server.py
```

Optional HTTP transport for local demos:

```powershell
python implementation\mcp_server.py --transport http --host 127.0.0.1 --port 8000
```

## Tools

The server exposes exactly these tools:

- `search`: query a table with optional `filters`, `columns`, `limit`, `offset`, `order_by`, and `descending`.
- `insert`: insert one row into a known table and return the inserted row.
- `aggregate`: run `count`, `avg`, `sum`, `min`, or `max`, with optional filters and `group_by`.

Example tool arguments:

```json
{
  "table": "students",
  "filters": { "cohort": "A1" },
  "columns": ["id", "name", "cohort", "score"],
  "order_by": "score",
  "descending": true,
  "limit": 5
}
```

```json
{
  "table": "students",
  "metric": "avg",
  "column": "score",
  "group_by": "cohort"
}
```

## Resources

- `schema://database`: full database schema as JSON.
- `schema://table/{table_name}`: one table schema as JSON, for example `schema://table/students`.

## Verification

Run automated tests:

```powershell
python -m pytest implementation\tests -q
```

Run the protocol-level verification script:

```powershell
python implementation\verify_server.py
```

Expected checks:

- discovers `search`, `insert`, and `aggregate`
- discovers `schema://database`
- discovers `schema://table/{table_name}`
- runs valid search, insert, and aggregate calls
- reads both schema resources
- returns a clear error for an invalid table

This solution was verified locally with Python 3.12 and FastMCP 3.4.2.

## Inspector

```powershell
powershell -ExecutionPolicy Bypass -File implementation\start_inspector.ps1
```

In MCP Inspector, connect to the local stdio server and check:

- the three tools appear with schemas
- both schema resources are visible/readable
- a valid `search` call succeeds
- an invalid table name returns an error

## Client Configuration Examples

Use the absolute path for this workspace:

```text
D:/DSA/Day26-Track3-MCP-tool-integration/implementation/mcp_server.py
```

Claude Code `.mcp.json`:

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "type": "stdio",
      "command": "python",
      "args": ["D:/DSA/Day26-Track3-MCP-tool-integration/implementation/mcp_server.py"],
      "env": {}
    }
  }
}
```

Codex `~/.codex/config.toml`:

```toml
[mcp_servers.sqlite_lab]
command = "python"
args = ["D:/DSA/Day26-Track3-MCP-tool-integration/implementation/mcp_server.py"]
```

Gemini CLI:

```powershell
gemini mcp add sqlite-lab python D:/DSA/Day26-Track3-MCP-tool-integration/implementation/mcp_server.py --description "SQLite lab FastMCP server" --timeout 10000
gemini mcp list
gemini --allowed-mcp-server-names sqlite-lab --yolo -p "Use the sqlite-lab MCP server and show the top 2 students by score."
```

## Demo Script

For a short video demo:

1. Run `python -m pytest implementation\tests -q`.
2. Run `python implementation\verify_server.py`.
3. Open Inspector and show the tool/resource list.
4. Call `search` for students in cohort `A1`.
5. Call `aggregate` for average score grouped by cohort.
6. Read `schema://table/students`.
7. Call `search` with table `missing_table` to show validation.
