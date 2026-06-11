from dataclasses import dataclass
from typing import Any

from shared.config import MODEL_GENERAL_AGENT
from shared.llm import get_llm


@dataclass
class RAGDependencies:
    """Dependencias del agente RAG."""
    llm: Any
    tickets: list[dict]


def build_dependencies(
    tickets: list[dict] | None = None,
    model: str | None = None,
) -> RAGDependencies:
    """Prepara el LLM y los tickets de ejemplo."""
    if tickets is None:
        tickets = [
            {
                "id": 1,
                "title": "Error al generar factura en Odoo",
                "description": "Al intentar confirmar una factura aparece el error 'account.move not found'.",
                "resolution": "El problema se debía a un módulo de contabilidad desactualizado. Se actualizó el módulo account desde el panel de aplicaciones y se reinició el servidor.",
            },
            {
                "id": 2,
                "title": "No puedo acceder al módulo de ventas",
                "description": "El usuario no ve el menú de ventas tras el login.",
                "resolution": "El usuario no tenía permisos asignados al grupo 'Sales / User'. Se añadió el usuario al grupo desde Ajustes > Usuarios.",
            },
            {
                "id": 3,
                "title": "Correos entrantes no se procesan",
                "description": "Los correos que llegan al servidor no generan tickets automáticamente.",
                "resolution": "El cron 'Mail Inbox: Process intake queue' estaba desactivado. Se activó desde Ajustes > Técnico > Acciones programadas.",
            },
        ]
    return RAGDependencies(llm=get_llm(model or MODEL_GENERAL_AGENT), tickets=tickets)