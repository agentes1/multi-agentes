from langchain_core.runnables import RunnableConfig
from shared.odoo_notifier import OdooNotifier


def get_notify_partner_id(config: RunnableConfig) -> int | None:
    """Lee el partner que recibirá la notificación."""
    value = config.get("configurable", {}).get("notify_partner_id") or config.get("configurable", {}).get("partner_id")
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def notify_agent_progress(config: RunnableConfig, title: str, message: str, type_: str = "info") -> bool:
    """Envía progreso del agente a Odoo si hay partner."""
    partner_id = get_notify_partner_id(config)
    return bool(partner_id and OdooNotifier().notify_partner(partner_id=partner_id, title=title, message=message, type=type_))