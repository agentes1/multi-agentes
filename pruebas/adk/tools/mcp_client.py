import asyncio
from pathlib import Path

from mcp.client.stdio import stdio_client


class MCPClient:

    def __init__(self):
        self.session = None

    async def connect(self):

        mcp_path = Path(__file__).resolve().parents[2] / "mcp" / "mcp_servidor_precios.py"

        self.session = await stdio_client(
            command="python",
            args=[str(mcp_path)]
        )

        # 🔥 handshake automático correcto
        await self.session.initialize()

    async def call_tool(self, tool_name, arguments):

        if self.session is None:
            await self.connect()

        result = await self.session.call_tool(
            tool_name,
            arguments
        )

        return result