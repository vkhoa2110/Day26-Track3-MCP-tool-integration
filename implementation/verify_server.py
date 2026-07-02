from __future__ import annotations

import asyncio
import json
import os
import tempfile
import uuid
from pathlib import Path

from fastmcp import Client

try:
    VERIFY_DB_PATH = Path(tempfile.gettempdir()) / "sqlite_lab_mcp_verify.sqlite3"
    os.environ["SQLITE_LAB_DB"] = str(VERIFY_DB_PATH)
    from .init_db import create_database

    create_database(VERIFY_DB_PATH, reset=True)
    from .mcp_server import mcp
except ImportError:
    VERIFY_DB_PATH = Path(tempfile.gettempdir()) / "sqlite_lab_mcp_verify.sqlite3"
    os.environ["SQLITE_LAB_DB"] = str(VERIFY_DB_PATH)
    from init_db import create_database

    create_database(VERIFY_DB_PATH, reset=True)
    from mcp_server import mcp


def _content_to_text(content) -> str:
    if hasattr(content, "text"):
        return content.text
    return str(content)


async def verify() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool_names = sorted(tool.name for tool in tools)
        print(f"Tools discovered: {tool_names}")
        assert {"search", "insert", "aggregate"}.issubset(tool_names)

        resources = await client.list_resources()
        resource_uris = sorted(str(resource.uri) for resource in resources)
        print(f"Resources discovered: {resource_uris}")
        assert "schema://database" in resource_uris

        templates = await client.list_resource_templates()
        template_uris = sorted(str(template.uriTemplate) for template in templates)
        print(f"Resource templates discovered: {template_uris}")
        assert "schema://table/{table_name}" in template_uris

        search_result = await client.call_tool(
            "search",
            {
                "table": "students",
                "filters": {"cohort": "A1"},
                "columns": ["id", "name", "cohort", "score"],
                "order_by": "score",
                "descending": True,
                "limit": 5,
            },
        )
        print(f"Search result: {json.dumps(search_result.structured_content, indent=2)}")

        aggregate_result = await client.call_tool(
            "aggregate",
            {"table": "students", "metric": "avg", "column": "score", "group_by": "cohort"},
        )
        print(f"Aggregate result: {json.dumps(aggregate_result.structured_content, indent=2)}")

        insert_result = await client.call_tool(
            "insert",
            {
                "table": "students",
                "values": {
                    "name": "Minh Ho",
                    "cohort": "A1",
                    "email": f"minh.ho.{uuid.uuid4().hex[:8]}@example.edu",
                    "score": 89.5,
                },
            },
        )
        print(f"Insert result: {json.dumps(insert_result.structured_content, indent=2)}")

        schema_contents = await client.read_resource("schema://database")
        print(f"Database schema sample: {_content_to_text(schema_contents[0])[:300]}...")

        table_schema_contents = await client.read_resource("schema://table/students")
        print(f"Students schema: {_content_to_text(table_schema_contents[0])}")

        invalid_result = await client.call_tool(
            "search",
            {"table": "missing_table"},
            raise_on_error=False,
        )
        assert invalid_result.is_error
        print(f"Invalid request error: {_content_to_text(invalid_result.content[0])}")

    print("Verification passed.")


if __name__ == "__main__":
    asyncio.run(verify())
