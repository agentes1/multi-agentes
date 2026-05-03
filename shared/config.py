from pathlib import Path
import os

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent

# En desarrollo local priorizamos el .env de la raiz si existe, pero
# mantenemos compatibilidad con shared/.env porque Docker Compose del proyecto
# lo usa como origen de variables para el backend.
load_dotenv(ROOT_DIR / ".env")
load_dotenv(ROOT_DIR / "shared" / ".env", override=False)

# CREDENCIALES MCP SERVER DE ODOO
URL = os.getenv("URL")
DB = os.getenv("DB")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

# VARIABLES DE llm.py
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# CREDENCIALES ODOO
ODOO_BASE_URL = os.getenv("ODOO_BASE_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USERNAME = os.getenv("ODOO_USERNAME")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD")

# Modelo por agente — si no se define, hereda OLLAMA_MODEL
MODEL_INTAKE_AGENT = os.getenv("MODEL_INTAKE_AGENT") or OLLAMA_MODEL
MODEL_BUDGET_AGENT = os.getenv("MODEL_BUDGET_AGENT") or OLLAMA_MODEL
MODEL_GENERAL_AGENT = os.getenv("MODEL_GENERAL_AGENT") or OLLAMA_MODEL
MODEL_EVAL_JUDGE = os.getenv("MODEL_EVAL_JUDGE") or OLLAMA_MODEL
