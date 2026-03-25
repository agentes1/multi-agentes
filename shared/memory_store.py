import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from schemas.budget import RetrievedQuoteMemory, StoredQuoteMemory
from shared.config import MEMORY_FILE_PATH


# clase para gestionar histórico de presupuestos
class QuoteMemoryStore:
    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path or MEMORY_FILE_PATH
        self.file_path.parent.mkdir(
            parents=True, exist_ok=True
        )  # crea carpeta contenedora si no existe
        self._ensure_file_exists()

    # crear fichero si no existe
    def _ensure_file_exists(self) -> None:
        if not self.file_path.exists():
            self.file_path.write_text("{}", encoding="utf-8")

    # carga y devuelve todo el contenido del fichero JSON
    def _load_all(self) -> dict[str, list[dict[str, Any]]]:
        try:
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        except Exception:
            return {}  # modificar más adelante para mayor especifidad

    # guarda en el disco todo el contenido de la memoria
    def _save_all(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self.file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # devuelve historial completo
    def get_company_history(self, company_name: str) -> list[dict[str, Any]]:
        data = self._load_all()
        return data.get(company_name, [])

    # devuelve resumen estructurado del último presupuesto de una empresa
    def get_last_quote_memory(self, company_name: str) -> RetrievedQuoteMemory:
        history = self.get_company_history(company_name)

        if not history:
            return RetrievedQuoteMemory(company_name=company_name)

        last_item = history[-1]
        quote_result = last_item.get("quote_result", {})

        lines = quote_result.get("lines", [])
        last_product_codes = [
            line.get("product_code") for line in lines if line.get("product_code")
        ]

        return RetrievedQuoteMemory(
            company_name=company_name,
            last_quote_total=quote_result.get("total"),
            last_quote_date=last_item.get("timestamp"),
            last_product_codes=last_product_codes,
            quote_count=len(history),
        )

    # añade presupuesto nuevo al histórico
    def append_quote(self, item: StoredQuoteMemory) -> None:
        data = self._load_all()
        company_history = data.setdefault(item.company_name, [])
        company_history.append(item.model_dump())
        self._save_all(data)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(UTC).isoformat()
