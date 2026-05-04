SALES_AGENT_NAME = "sales_agent"


def build_sales_entry_reply(ticket: dict) -> str:
    title = str(ticket.get("name") or ticket.get("subject") or "").strip()
    if title:
        return (
            f"He detectado que '{title}' parece una solicitud comercial. "
            "Voy a ayudarte por este chat a concretar el interés de venta, el alcance y el siguiente paso comercial."
        )
    return (
        "He detectado una solicitud comercial. Voy a ayudarte por este chat a concretar el interés de venta, "
        "el alcance y el siguiente paso comercial."
    )


def build_sales_discuss_reply(payload: dict) -> str:
    body = str(payload.get("body") or "").strip()
    if not body:
        return (
            "Cuéntame qué necesidad comercial tenéis: captación de leads, seguimiento de oportunidades, "
            "pipeline de ventas, reporting o automatización comercial."
        )

    return (
        "He entendido que se trata de una conversación comercial. Para orientarlo bien, indícame qué objetivo "
        "tenéis ahora mismo: captar leads, organizar oportunidades, mejorar el pipeline, automatizar seguimiento "
        "o preparar una propuesta comercial. Cuando lo veas correcto, dime 'sí' o 'adelante' y lo marcaré como "
        "'Ready for next stage' para crear la oportunidad comercial en CRM."
    )
