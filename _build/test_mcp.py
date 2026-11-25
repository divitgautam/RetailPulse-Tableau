"""Smoke test: start the cwtwb MCP server over stdio, list its tools, open the workbook and list worksheets."""
import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(sys.executable).with_name("cwtwb.exe")


async def main() -> None:
    params = StdioServerParameters(command=str(EXE), args=["mcp"])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = (await s.list_tools()).tools
            print(f"tools: {len(tools)}")
            out = await s.call_tool("open_workbook", {"file_path": str(ROOT / "RetailPulse-Tableau.twb")})
            print(out.content[0].text.splitlines()[0])
            out = await s.call_tool("list_worksheets", {})
            print(out.content[0].text)


asyncio.run(main())
