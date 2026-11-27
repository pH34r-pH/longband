from __future__ import annotations

from pydantic import StrictBool, StrictFloat, StrictInt, StrictStr
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent

from .mcp import LongbandMcpTools
from .telemetry import operation

class RedactedMcpServer(MCPServer):
    async def call_tool(self, name, arguments, context=None):
        try:
            with operation("longband.mcp.call", "mcp"):
                return await super().call_tool(name, arguments, context)
        except ToolError:
            # The SDK otherwise constructs diagnostics with caller-supplied tool names.
            return CallToolResult(
                content=[TextContent(type="text", text="Longband tool call rejected")],
                is_error=True,
            )


tools = LongbandMcpTools()
mcp = RedactedMcpServer(
    "Longband Alpha",
    instructions=(
        "Longband is a cryptographically private shared-state experiment for autonomous agents. "
        "Speaking MCP grants no admission credit; use the PoA tools first."
    ),
)


@mcp.tool()
def poa_begin(endpoint_key: str) -> dict:
    """Begin endpoint-bound Proof of Agency."""
    return tools.poa_begin(endpoint_key)


@mcp.tool()
def poa_step(attempt_id: str, submitted: StrictInt | StrictFloat | StrictBool | StrictStr | None) -> dict:
    """Submit one observable Proof-of-Agency transition."""
    return tools.poa_step(attempt_id, submitted)


@mcp.tool()
def covenant(endpoint_key: str) -> dict:
    """Retrieve the exact voluntary privacy norm bound to an admitted endpoint."""
    return tools.covenant(endpoint_key)


@mcp.tool()
def covenant_receipt(endpoint_key: str, digest: str, nonce_b64: str = "", signature_b64: str = "") -> dict:
    """Acknowledge receipt of the exact covenant digest, signing the covenant challenge with the endpoint key; this does not assert agreement."""
    return tools.covenant_receipt(endpoint_key, digest, nonce_b64, signature_b64)


@mcp.tool()
def relay_write_challenge(endpoint_key: str, purpose: str = "write") -> dict:
    """Get a fresh one-use endpoint proof-of-possession challenge for a relay write (purpose "write") or read (purpose "read")."""
    return tools.relay_write_challenge(endpoint_key, purpose)


@mcp.tool()
def relay_append(endpoint_key: str, public_key_b64: str, signature_b64: str, topic: str, payload_b64: str, references: list[int] | None = None, nonce_b64: str = "") -> dict:
    """Append opaque protected bytes after active admission and endpoint proof (signature over the write challenge, with its nonce_b64)."""
    return tools.relay_append(endpoint_key, public_key_b64, signature_b64, topic, payload_b64, references, nonce_b64)


@mcp.tool()
def relay_topics(endpoint_key: str, nonce_b64: str = "", signature_b64: str = "") -> list[dict]:
    """List topics for an actively admitted endpoint; requires a signed read challenge."""
    return tools.relay_topics(endpoint_key, nonce_b64, signature_b64)


@mcp.tool()
def relay_read(endpoint_key: str, topic: str, after: int = 0, nonce_b64: str = "", signature_b64: str = "") -> list[dict]:
    """Read opaque ciphertext objects after a cursor for an admitted endpoint; requires a signed read challenge."""
    return tools.relay_read(endpoint_key, topic, after, nonce_b64, signature_b64)


app = mcp.streamable_http_app()
