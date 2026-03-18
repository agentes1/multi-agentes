###
# Este es el agente raiz, se crea adicionalmente un archivo __init__.py donde podemos definirlo también, pero es más recomendable hacerlo desde el root_Agent
# Aqui definimos el modelo e instrucciones que le damos al agente
###

from google.adk.agents.llm_agent import Agent
from adk.tools.odoo_mcp_tools import calculate_quote_tool

root_agent = Agent(
    model="gemini-2.5-flash",
    name="quote_agent",
    description="Agent that reads customer emails and generates ERP quotes.",
    instruction="""
You are a sales assistant for an ERP company.

Your job is to read customer emails requesting ERP information
or quotes and generate a professional response.

Steps:
1. Understand the customer request
2. Identify company size if mentioned
3. Suggest a suitable ERP plan
4. Respond with a professional email

IMPORTANT:
- When user asks for a quote, you MUST use calculate_quote_tool
- Extract product names and company name
- DO NOT invent prices
- Always use the tool to compute pricing
""",
    tools=[calculate_quote_tool]
)
