import pytest
from mcp import Client
from mcp_types import ListToolsResult

from longband_relay.mcp_server import mcp


@pytest.mark.asyncio
async def test_real_mcp_v2_server_discovers_longband_tools():
    async with Client(mcp) as client:
        result = await client.list_tools()
        assert isinstance(result, ListToolsResult)
        names = {tool.name for tool in result.tools}
        assert {
            "poa_begin",
            "poa_step",
            "covenant",
            "covenant_receipt",
            "relay_write_challenge",
            "relay_append",
            "relay_read",
            "relay_topics",
        } <= names
        assert result.next_cursor is None
        assert client.protocol_version == "2026-07-28"
