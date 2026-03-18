from adk.tools.mcp_client import MCPClient

mcp_client = MCPClient()


async def calculate_quote_tool(product_codes: list[str], company_name: str):

    result = await mcp_client.call_tool(
        "calculate_quote",
        {
            "product_codes": product_codes,
            "company_name": company_name
        }
    )

    return result