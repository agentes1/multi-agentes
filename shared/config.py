from dotenv import load_dotenv
import os
load_dotenv()

#/CREDENCIALES MCP SERVER DE ODOO/
URL = os.getenv("URL")
DB = os.getenv("DB")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

#/VARIABLES DE llm.py/
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
OLLAMA_TEMPERATURE = os.getenv("OLLAMA_TEMPERATURE")

#/CREDEMCIALES ODOO/
ODOO_BASE_URL = os.getenv("ODOO_BASE_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USERNAME = os.getenv("ODOO_USERNAME")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
