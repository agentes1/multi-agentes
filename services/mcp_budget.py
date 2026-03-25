import json
import sys
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from shared.config import MCP_SERVER_PATH


# traduce "MCP" a "datos útiles para el agente"
# abrir conexión con el servidor MCP
# cargar tools publicadas por el servidor
# ejecutar tools necesarias
# adaptar respuesta a formato Python útil
class MCPBudgetService:
    # construye cliente MCP
    def _build_client(self) -> MultiServerMCPClient:
        if not MCP_SERVER_PATH.exists():
            raise FileNotFoundError(f"No encuentro el servidor MCP en esta ruta: {MCP_SERVER_PATH}")

        # cliente que permite conectarse a uno o varios servidores MCP
        return MultiServerMCPClient(
            {
                # nombre interno con el que luego abres sesión
                "odoo_budget": {
                    "transport": "stdio",  # cliente y servidor se comunican por stdin/stdout
                    "command": sys.executable,  # lanzar servidor con el mismo intérprete (el mismo entorno) donde se está ejecutando el proyecto
                    "args": [str(MCP_SERVER_PATH)],  # ruta al mcp
                }
            }
        )

    # convierte formato de respuesta MCP a dict -> a veces MCP devuelve cosas distintas
    def _parse_mcp_result(self, result: Any) -> dict[str, Any]:
        if isinstance(result, dict):
            return result

        if isinstance(result, list) and result:
            first_item = result[0]

            if isinstance(first_item, dict):
                text = first_item.get("text")

                if isinstance(text, str):
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError as exc:
                        raise ValueError(
                            f"La respuesta MCP no contiene un JSON válido: {text}"
                        ) from exc

        raise ValueError(f"Formato de respuesta MCP no soportado: {result}")

    # devuelve contexto procesado
    async def get_budget_context(
        self,
        company_name: str,
        product_codes: list[str],
    ) -> dict[str, Any]:
        client = self._build_client()

        async with client.session("odoo_budget") as session:
            tools = await load_mcp_tools(session)
            tools_by_name = {tool.name: tool for tool in tools}

            customer_profile_raw = await tools_by_name["get_customer_profile"].ainvoke(
                {"company_name": company_name}
            )

            quote_raw = await tools_by_name["calculate_quote"].ainvoke(
                {
                    "product_codes": product_codes,
                    "company_name": company_name,
                }
            )

            customer_profile = self._parse_mcp_result(customer_profile_raw)
            quote = self._parse_mcp_result(quote_raw)

            return {
                "customer_profile": customer_profile,
                "quote": quote,
            }
