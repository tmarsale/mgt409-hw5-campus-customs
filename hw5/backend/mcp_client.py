"""How the FastAPI backend talks to the campus-customs MCP server.

- Reads use one long-lived server process with writes locked (the same
  minimal environment the agents get).
- A write (a human-approved payment) starts a separate, short-lived server
  with writes unlocked for that single call, then shuts it down.
"""

import asyncio
import sys
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

import config
from team import mcp_server_env


class ToolFailed(Exception):
    """The MCP tool returned an error (for example, an unknown ticket)."""


def _transport(env: dict[str, str]) -> StdioTransport:
    return StdioTransport(command=sys.executable, args=[str(config.MCP_SERVER)], env=env, cwd=str(config.HW5_DIR))


async def _call(client: Client, tool: str, args: dict[str, Any] | None) -> dict:
    result = await client.call_tool(tool, args or {}, raise_on_error=False)
    if result.is_error:
        raise ToolFailed(" ".join(getattr(b, "text", "") for b in result.content).strip())
    return result.structured_content or {}


class ShopMCP:
    def __init__(self) -> None:
        self._client: Client | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self._client = Client(_transport(mcp_server_env()))
        await self._client.__aenter__()

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def read(self, tool: str, args: dict[str, Any] | None = None) -> dict:
        """Call a read-only tool on the long-lived, write-locked server."""
        if tool in config.HUMAN_ONLY_TOOLS:
            raise PermissionError(f"{tool} must go through write_with_approval().")
        async with self._lock:
            if self._client is None:
                await self.start()
            return await _call(self._client, tool, args)

    async def write_with_approval(self, tool: str, args: dict[str, Any]) -> dict:
        """Call a human-only write tool on a one-off server with writes unlocked.

        The caller has already checked the human's approval code; the server
        checks it again against CAMPUS_CUSTOMS_APPROVAL_CODE.
        """
        if tool not in config.HUMAN_ONLY_TOOLS:
            raise ValueError(f"{tool} is not a write tool.")
        env = mcp_server_env()
        env["CAMPUS_CUSTOMS_ALLOW_WRITES"] = "1"
        env["CAMPUS_CUSTOMS_APPROVAL_CODE"] = config.approval_code()
        async with Client(_transport(env)) as client:
            return await _call(client, tool, args)
