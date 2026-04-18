from dotenv import load_dotenv
load_dotenv()

#/CREDENCIALES MCP SERVER DE ODOO/
URL = get_env_variable("URL")
DB = get_env_variable("DB")
USERNAME = get_env_variable("USERNAME")
PASSWORD = get_env_variable("PASSWORD")

#/VARIABLES DE llm.py/
OLLAMA_MODEL = get_env_variable("OLLAMA_MODEL")
OLLAMA_TEMPERATURE = get_env_variable("OLLAMA_TEMPERATURE")

#/CREDEMCIALES ODOO/
ODOO_BASE_URL = get_env_variable("ODOO_BASE_URL")
ODOO_DB = get_env_variable("ODOO_DB")
ODOO_USERNAME = get_env_variable("ODOO_USERNAME")
ODOO_PASSWORD = get_env_variable("ODOO_PASSWORD")
