from typing import Annotated, TypedDict

from langgraph.graph.message import (
    add_messages,  # para añadir el valor de las claves de estado en vez de sobreescribir
)


# definir estado compartido del grafo para presupuesto
class BudgetState(TypedDict):
    # guarda el historial de mensajes del flujo
    messages: Annotated[list, add_messages]
    normalized_request: dict  # solicitud interpretada y normalizada
    selected_products: list[str]  # lista productos o módulos
    retrieved_memory: dict  # memoria recuperada
    customer_profile: dict  # perfil del cliente
    quote_result: dict  # resultado estructurado del presupuesto
    final_text: str  # texto final redactado del presupuesto
    error: str | None  # error producido en el flujo, None si no hay error
