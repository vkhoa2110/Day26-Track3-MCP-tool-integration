from __future__ import annotations

import asyncio

from fastmcp import Client

from implementation.mcp_server import mcp


def test_mcp_client_discovers_tools_and_resources():
    async def run():
        async with Client(mcp) as client:
            tool_names = {tool.name for tool in await client.list_tools()}
            resource_uris = {str(resource.uri) for resource in await client.list_resources()}
            template_uris = {str(template.uriTemplate) for template in await client.list_resource_templates()}

            assert tool_names == {"search", "insert", "aggregate"}
            assert "schema://database" in resource_uris
            assert "schema://table/{table_name}" in template_uris

            result = await client.call_tool(
                "search",
                {"table": "students", "filters": {"cohort": "A1"}, "limit": 2},
            )
            assert result.structured_content["count"] == 2

            invalid = await client.call_tool("search", {"table": "missing"}, raise_on_error=False)
            assert invalid.is_error

    asyncio.run(run())
