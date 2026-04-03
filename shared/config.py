from pathlib import Path

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent.parent

MCP_SERVER_PATH = PROJECT_ROOT / "mcp" / "mcp_servidor_precios.py"
MEMORY_FILE_PATH = PROJECT_ROOT / "memory_data" / "quote_memory.json"

OLLAMA_MODEL = "qwen3:4b"
OLLAMA_TEMPERATURE = 0
