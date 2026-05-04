from pathlib import Path
import os

from dotenv import load_dotenv


# Carga de entorno (primero .env raíz, luego shared/.env sin sobrescribir)
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")
load_dotenv(ROOT_DIR / "shared" / ".env", override=False)


def _env(name: str) -> str | None:
    """Lee variable de entorno limpiando espacios y comillas."""
    value = os.getenv(name)
    return value.strip().strip("\"'") if value else None


# MCP Server (Odoo tools)
URL = _env("URL")
DB = _env("DB")
USERNAME = _env("USERNAME")
PASSWORD = _env("PASSWORD")

# LLM (Ollama)
OLLAMA_MODEL = _env("OLLAMA_MODEL")
OLLAMA_TEMPERATURE = _env("OLLAMA_TEMPERATURE")
OLLAMA_BASE_URL = _env("OLLAMA_BASE_URL")

# Odoo (ERP real)
ODOO_BASE_URL = _env("ODOO_BASE_URL")
ODOO_DB = _env("ODOO_DB")
ODOO_USERNAME = _env("ODOO_USERNAME")
ODOO_PASSWORD = _env("ODOO_PASSWORD")

# Modelos por agente (con fallback al modelo base)
OLLAMA_MODEL_OVERRIDE = _env("OLLAMA_MODEL_OVERRIDE") or OLLAMA_MODEL
MODEL_BUDGET_AGENT = OLLAMA_MODEL_OVERRIDE or OLLAMA_MODEL
MODEL_INTAKE_AGENT = OLLAMA_MODEL_OVERRIDE or OLLAMA_MODEL
MODEL_DISCUSS_AGENT = OLLAMA_MODEL_OVERRIDE or OLLAMA_MODEL
MODEL_ENTRY_AGENT = OLLAMA_MODEL_OVERRIDE or OLLAMA_MODEL
MODEL_GENERAL_AGENT = OLLAMA_MODEL_OVERRIDE or OLLAMA_MODEL