from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

try:
    from .db import SQLiteAdapter, ValidationError
    from .init_db import DEFAULT_DB_PATH, create_database
except ImportError:
    from db import SQLiteAdapter, ValidationError
    from init_db import DEFAULT_DB_PATH, create_database


DB_PATH = Path(DEFAULT_DB_PATH)
_adapter: SQLiteAdapter | None = None

mcp = FastMCP("SQLite Lab MCP Server")


def get_adapter() -> SQLiteAdapter:
    global _adapter
    if _adapter is None:
        create_database(DB_PATH)
        _adapter = SQLiteAdapter(DB_PATH)
    return _adapter


def _run_safely(operation):
    try:
        return operation()
    except ValidationError as exc:
        raise ToolError(str(exc), log_level=logging.WARNING) from exc
    except sqlite3.Error as exc:
        raise ToolError(f"database error: {exc}", log_level=logging.WARNING) from exc


@mcp.tool(name="search")
def search(
    table: str,
    filters: dict[str, Any] | list[dict[str, Any]] | None = None,
    columns: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str | None = None,
    descending: bool = False,
) -> dict[str, Any]:
    """Search rows with optional filters, selected columns, ordering, and pagination."""
    return _run_safely(
        lambda: get_adapter().search(
            table=table,
            filters=filters,
            columns=columns,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending,
        )
    )


@mcp.tool(name="insert")
def insert(table: str, values: dict[str, Any]) -> dict[str, Any]:
    """Insert one row into a known table and return the inserted row."""
    return _run_safely(lambda: get_adapter().insert(table=table, values=values))


@mcp.tool(name="aggregate")
def aggregate(
    table: str,
    metric: str,
    column: str | None = None,
    filters: dict[str, Any] | list[dict[str, Any]] | None = None,
    group_by: str | list[str] | None = None,
) -> dict[str, Any]:
    """Run count, avg, sum, min, or max against a known table."""
    return _run_safely(
        lambda: get_adapter().aggregate(
            table=table,
            metric=metric,
            column=column,
            filters=filters,
            group_by=group_by,
        )
    )


@mcp.resource("schema://database", mime_type="application/json")
def database_schema() -> str:
    """Return the full database schema as JSON."""
    return json.dumps(get_adapter().get_database_schema(), indent=2)


@mcp.resource("schema://table/{table_name}", mime_type="application/json")
def table_schema(table_name: str) -> str:
    """Return one table schema as JSON."""
    return _run_safely(lambda: json.dumps(get_adapter().get_table_schema(table_name), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SQLite lab FastMCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport to use.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP/SSE transports.")
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP/SSE transports.")
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
