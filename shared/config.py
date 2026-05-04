from pathlib import Path
import os

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent

load_dotenv(ROOT_DIR / ".env")
load_dotenv(ROOT_DIR / "shared" / ".env", override=False)


def _env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip().strip("\"'") if value else None


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "y", "on"}


def _env_float(name: str, default: float) -> float:
    value = _env(name)
    if value is None:
        return default
    return float(value)


# MCP Server / Odoo tools
URL = _env("URL") or "http://web:8069"
DB = _env("DB") or "odoo"
USERNAME = _env("USERNAME") or "odoo"
PASSWORD = _env("PASSWORD")

# Odoo ERP real
ODOO_BASE_URL = _env("ODOO_BASE_URL") or URL
ODOO_DB = _env("ODOO_DB") or DB
ODOO_USERNAME = _env("ODOO_USERNAME") or USERNAME
ODOO_PASSWORD = _env("ODOO_PASSWORD") or PASSWORD

# LLM / Ollama
OLLAMA_MODEL = _env("OLLAMA_MODEL") or "qwen3:4b"
OLLAMA_TEMPERATURE = _env_float("OLLAMA_TEMPERATURE", 0.0)
OLLAMA_BASE_URL = _env("OLLAMA_BASE_URL") or "http://ollama:11434"

# Router
ROUTER_EMBEDDINGS_ENABLED = _env_bool("ROUTER_EMBEDDINGS_ENABLED", False)
ROUTER_EMBED_MODEL = _env("ROUTER_EMBED_MODEL") or OLLAMA_MODEL

# Modelos por agente
OLLAMA_MODEL_OVERRIDE = _env("OLLAMA_MODEL_OVERRIDE")

MODEL_BUDGET_AGENT = _env("MODEL_BUDGET_AGENT") or OLLAMA_MODEL_OVERRIDE or OLLAMA_MODEL
MODEL_INTAKE_AGENT = _env("MODEL_INTAKE_AGENT") or OLLAMA_MODEL_OVERRIDE or OLLAMA_MODEL
MODEL_DISCUSS_AGENT = _env("MODEL_DISCUSS_AGENT") or OLLAMA_MODEL_OVERRIDE or OLLAMA_MODEL
MODEL_ENTRY_AGENT = _env("MODEL_ENTRY_AGENT") or OLLAMA_MODEL_OVERRIDE or OLLAMA_MODEL
MODEL_GENERAL_AGENT = _env("MODEL_GENERAL_AGENT") or OLLAMA_MODEL_OVERRIDE or OLLAMA_MODEL
MODEL_SALES_AGENT = _env("MODEL_SALES_AGENT") or OLLAMA_MODEL_OVERRIDE or OLLAMA_MODEL
MODEL_EVAL_JUDGE = _env("MODEL_EVAL_JUDGE") or OLLAMA_MODEL_OVERRIDE or OLLAMA_MODEL