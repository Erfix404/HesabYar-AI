"""End-to-end stdio smoke test for the HesabYar MCP server.

Spawns `uv run hesabyar-mcp` as a real subprocess, performs the MCP
handshake, lists tools, and calls two tools. Exits non-zero on failure.

Run:  uv run python scripts/mcp_smoke.py
"""

from __future__ import annotations

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows console (cp1256) safe


async def main() -> None:
    params = StdioServerParameters(command="uv", args=["run", "hesabyar-mcp"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print("server:", init.serverInfo.name, "| protocol:", init.protocolVersion)

            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print("tools:", names)
            assert len(names) == 10, f"expected 10 tools, got {names}"

            res = await session.call_tool(
                "check_tax_parameter", {"name": "vat_rate", "on_date": "1405/06/01"}
            )
            text = res.content[0].text
            print("vat_rate ->", text.replace("\n", " ")[:160])
            assert '"value": "0.10"' in text, text

            res2 = await session.call_tool("moadian_error", {"code": "4110"})
            text2 = res2.content[0].text
            print("4110 ->", text2.replace("\n", " ")[:160])
            assert '"found": true' in text2, text2

    print("MCP stdio smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
