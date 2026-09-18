import pytest
from mcp import Client

from longband_relay.mcp_server import mcp


@pytest.mark.asyncio
async def test_real_mcp_v2_server_discovers_longband_tools():
    async with Client(mcp) as client:
        result = await client.list_tools()
        # MCP SDK v2 returns (tools, metadata) for this high-level client call.
        tools = result[0] if isinstance(result, tuple) else result
        names = {tool.name for tool in tools}
        assert {
            "poa_begin",
            "poa_step",
            "covenant",
            "covenant_receipt",
            "relay_write_challenge",
            "relay_append",
            "relay_read",
        } <= names
        assert client.protocol_version == "2026-07-28"
