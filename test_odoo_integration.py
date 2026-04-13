import asyncio
import sys

from shared.config import MCP_SERVER_PATH
from services.mcp_budget import MCPBudgetService

async def main():
    print(f"Using MCP Server at: {MCP_SERVER_PATH}")
    service = MCPBudgetService()
    try:
        res = await service.get_budget_context("ACME", ["crm_base", "odoo_connector"])
        print("Success!")
        print("Customer Profile:", res['customer_profile'])
        print("Quote:", res['quote'])
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
