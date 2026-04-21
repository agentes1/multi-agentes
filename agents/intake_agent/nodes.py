import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from odoo.helpers import Table
from odoo.tools import build_odoo_tools
from shared.catalog import (
    CANONICAL_TYPE_TO_ODOO_NAME,
    DEFAULT_TICKET_BLUEPRINTS,
    NORMALIZATION_SYSTEM_PROMPT,
    PRIORITY_TO_ODOO,
    normalize_priority,
    normalize_ticket_type,
)
from .dependencies import TicketAgentDependencies
from .state import TicketAgentState


def _get_deps(config: RunnableConfig) -> TicketAgentDependencies:
    return config["configurable"]["deps"]


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _titleize_name(value: str) -> str:
    parts = [part for part in re.split(r"[\s._\-+]+", value) if part]
    return " ".join(part.capitalize() for part in parts)


def _extract_email_parts(email: str | None) -> tuple[str | None, str | None]:
    email = _safe_text(email)
    if not email or "@" not in email:
        return None, None

    local_part, domain = email.split("@", 1)
    return local_part.strip(), domain.strip().lower()


def _guess_partner_name(sender_name: str | None, sender_email: str | None) -> str | None:
    explicit_name = _safe_text(sender_name)
    if explicit_name:
        return explicit_name

    local_part, _ = _extract_email_parts(sender_email)
    if not local_part:
        return None

    return _titleize_name(local_part)


def _guess_company_name_from_email(sender_email: str | None) -> str | None:
    _, domain = _extract_email_parts(sender_email)
    if not domain:
        return None

    domain_parts = [part for part in domain.split(".") if part]
    if len(domain_parts) < 2:
        return None

    company_token = domain_parts[-2]
    if len(domain_parts) >= 3 and domain_parts[-2] in {"com", "net", "org", "co"}:
        company_token = domain_parts[-3]

    company_token = company_token.strip()
    if not company_token:
        return None

    if len(company_token) <= 4:
        return company_token.upper()

    return _titleize_name(company_token)


def _build_company_search_candidates(company_name: str | None, sender_email: str | None) -> list[str]:
    candidates: list[str] = []

    explicit_company = _safe_text(company_name)
    if explicit_company:
        candidates.append(explicit_company)

    guessed_company = _guess_company_name_from_email(sender_email)
    if guessed_company:
        candidates.append(guessed_company)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)

    return deduped


def _find_company_partner(odoo, company_name: str | None, sender_email: str | None) -> dict[str, Any] | None:
    candidates = _build_company_search_candidates(company_name, sender_email)
    if not candidates:
        return None

    for candidate in candidates:
        exact_matches = odoo._query(
            Table.Contact,
            "search_read",
            [[("is_company", "=", True), ("name", "=ilike", candidate)]],
            {"fields": ["id", "name", "email", "is_company"], "limit": 1},
        )
        if exact_matches:
            return exact_matches[0]

    for candidate in candidates:
        fuzzy_matches = odoo._query(
            Table.Contact,
            "search_read",
            [[("is_company", "=", True), ("name", "ilike", candidate)]],
            {"fields": ["id", "name", "email", "is_company"], "limit": 1},
        )
        if fuzzy_matches:
            return fuzzy_matches[0]

    return None


def _build_partner_debug_trace(
    odoo,
    company_name: str | None,
    sender_email: str | None,
) -> dict[str, Any]:
    candidates = _build_company_search_candidates(company_name, sender_email)
    trace: dict[str, Any] = {
        "input_company_name": company_name,
        "sender_email": sender_email,
        "candidates": candidates,
        "exact_matches": [],
        "fuzzy_matches": [],
    }

    for candidate in candidates:
        exact_matches = odoo._query(
            Table.Contact,
            "search_read",
            [[("is_company", "=", True), ("name", "=ilike", candidate)]],
            {"fields": ["id", "name", "email", "is_company"], "limit": 5},
        )
        trace["exact_matches"].append({"candidate": candidate, "results": exact_matches})

    for candidate in candidates:
        fuzzy_matches = odoo._query(
            Table.Contact,
            "search_read",
            [[("is_company", "=", True), ("name", "ilike", candidate)]],
            {"fields": ["id", "name", "email", "is_company"], "limit": 5},
        )
        trace["fuzzy_matches"].append({"candidate": candidate, "results": fuzzy_matches})

    return trace


def _find_id_by_name(odoo, table: str, value: str | None) -> int | None:
    value = _safe_text(value)
    if not value:
        return None

    records = odoo._query(
        table,
        "search_read",
        [[("name", "=ilike", value)]],
        {"fields": ["id", "name"], "limit": 1},
    )
    if not records:
        return None
    return records[0]["id"]


def _find_tag_ids(odoo, tag_names: list[str]) -> list[int]:
    ids: list[int] = []

    for raw_tag in tag_names:
        tag_name = _safe_text(raw_tag)
        if not tag_name:
            continue

        records = odoo._query(
            Table.TicketTag,
            "search_read",
            [[("name", "=ilike", tag_name)]],
            {"fields": ["id", "name"], "limit": 1},
        )
        if records:
            ids.append(records[0]["id"])

    return ids


def _get_ticket_field_names(odoo) -> set[str]:
    fields_meta = odoo._query(
        Table.Ticket,
        "fields_get",
        [],
        {"attributes": ["string", "type"]},
    )
    return set(fields_meta.keys())


def _dedupe_tags(tag_names: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []

    for raw_tag in tag_names:
        tag_name = _safe_text(raw_tag)
        if not tag_name:
            continue

        key = tag_name.casefold()
        if key in seen:
            continue

        seen.add(key)
        deduped.append(tag_name)

    return deduped


def _build_ticket_defaults(
    normalized_type: str,
    raw_team: str | None,
    raw_category: str | None,
    raw_tags: list[str],
    normalized_priority: str,
) -> dict[str, Any]:
    blueprint = DEFAULT_TICKET_BLUEPRINTS.get(
        normalized_type,
        DEFAULT_TICKET_BLUEPRINTS["discard"],
    )

    tag_names = list(raw_tags) if isinstance(raw_tags, list) else []
    tag_names.extend(blueprint["default_tags"])

    if normalized_priority == "alta":
        tag_names.append("Urgente")

    return {
        "team_name": _safe_text(raw_team) or blueprint["team_name"],
        "ticket_type_name": blueprint["ticket_type"],
        "category_name": _safe_text(raw_category) or blueprint["category"],
        "tag_names": _dedupe_tags(tag_names),
        "priority_normalized": normalized_priority,
        "priority": PRIORITY_TO_ODOO[normalized_priority],
    }


def _collect_missing_essential_fields(
    company_name: str | None,
    raw_type: str | None,
) -> list[str]:
    missing_fields: list[str] = []

    if not _safe_text(company_name):
        missing_fields.append("compania")

    if not _safe_text(raw_type):
        missing_fields.append("tipo de ticket")

    return missing_fields


async def normalize_email_node(
    state: TicketAgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    deps = _get_deps(config)

    subject = state.get("email_subject", "") or ""
    body = state.get("email_body", "") or ""
    sender_email = state.get("sender_email", "") or ""
    sender_name = state.get("sender_name")

    user_prompt = f"""
Asunto: {subject}
Remitente email: {sender_email}
Remitente nombre: {sender_name}
Cuerpo:
{body}
""".strip()

    response = await deps.llm.ainvoke(
        [
            SystemMessage(content=NORMALIZATION_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
    )

    try:
        normalized = json.loads(response.content)
    except Exception as e:
        return {"error": f"No se pudo parsear el JSON del LLM: {e}"}

    title = _safe_text(normalized.get("title"))
    description = _safe_text(normalized.get("description"))

    if not title:
        return {"error": "El LLM no devolvió un title válido"}
    if not description:
        return {"error": "El LLM no devolvió un description válido"}

    normalized["title"] = title
    normalized["description"] = description
    normalized["customer_email"] = _safe_text(normalized.get("customer_email")) or _safe_text(sender_email)
    normalized["company_name"] = _safe_text(normalized.get("company_name")) or _guess_company_name_from_email(sender_email)
    normalized["partner_name"] = _safe_text(normalized.get("partner_name")) or _guess_partner_name(sender_name, sender_email)
    normalized["team"] = _safe_text(normalized.get("team"))
    normalized["ticket_type"] = _safe_text(normalized.get("ticket_type"))
    normalized["category"] = _safe_text(normalized.get("category"))
    normalized["stage"] = _safe_text(normalized.get("stage"))
    normalized["priority"] = _safe_text(normalized.get("priority"))

    tags = normalized.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    normalized["tags"] = [str(tag).strip() for tag in tags if str(tag).strip()]

    return {
        "normalized_ticket": normalized,
        "missing_fields": _collect_missing_essential_fields(
            company_name=normalized.get("company_name"),
            raw_type=normalized.get("ticket_type"),
        ),
    }


async def _run_tool_calls(response, tools: list) -> list[ToolMessage]:
    tool_map = {t.name: t for t in tools}
    results = []
    for tc in getattr(response, "tool_calls", []):
        tool = tool_map.get(tc["name"])
        if tool:
            try:
                output = await tool.ainvoke(tc.get("args", {}))
                results.append(ToolMessage(content=str(output), tool_call_id=tc.get("id", "")))
            except Exception as e:
                results.append(ToolMessage(content=f"Error: {e}", tool_call_id=tc.get("id", "")))
    return results


# TOOL-CALLING: el LLM consulta Odoo para enriquecer el contexto del ticket.
# Solo lectura — los errores son silenciosos para no bloquear el flujo principal.
# Las mutaciones (crear partner, crear ticket) ocurren en los nodos siguientes.
async def enrich_context_node(
    state: TicketAgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    if state.get("error"):
        return {}

    deps = _get_deps(config)
    normalized = state.get("normalized_ticket", {})
    company_name = normalized.get("company_name") or normalized.get("partner_name") or ""
    customer_email = normalized.get("customer_email") or ""

    prompt = (
        f"Consulta si el cliente existe en Odoo y obtén su historial. "
        f"Empresa: '{company_name}', email: '{customer_email}'."
    )

    try:
        tools = build_odoo_tools(deps.odoo_service)
        llm_with_tools = deps.llm.bind_tools(tools)
        response = await llm_with_tools.ainvoke([HumanMessage(content=prompt)])
        tool_messages = await _run_tool_calls(response, tools)
        return {"odoo_context": {"raw_results": [m.content for m in tool_messages]}}
    except Exception:
        return {"odoo_context": {}}


def ensure_partner_node(
    state: TicketAgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    if state.get("error"):
        return {}

    deps = _get_deps(config)
    normalized = state["normalized_ticket"]

    customer_email = normalized.get("customer_email")
    company_name = normalized.get("company_name")

    # sin empresa ni email identificable no hay a quién asociar el ticket
    if not customer_email and not company_name:
        return {
            "partner_id": None,
            "company_is_new": False,
            "debug_trace": {},
            "normalized_ticket": normalized,
        }

    odoo = deps.odoo_service._wrapper
    debug_trace = _build_partner_debug_trace(
        odoo,
        company_name=company_name,
        sender_email=customer_email,
    )

    existing_company = _find_company_partner(
        odoo,
        company_name=company_name,
        sender_email=customer_email,
    )
    if existing_company:
        normalized["company_name"] = existing_company["name"]
        return {
            "partner_id": existing_company["id"],
            "company_is_new": False,
            "debug_trace": {
                **debug_trace,
                "matched_company": existing_company,
                "company_resolution": "existing",
                "final_partner_id": existing_company["id"],
            },
            "normalized_ticket": normalized,
        }

    final_company_name = company_name or _guess_company_name_from_email(customer_email) or "Cliente nuevo"
    company_vals: dict[str, Any] = {
        "name": final_company_name,
        "is_company": True,
        "customer_rank": 1,
    }
    if customer_email:
        company_vals["email"] = customer_email

    partner_id = odoo._query(Table.Contact, "create", [company_vals])
    normalized["company_name"] = final_company_name

    return {
        "partner_id": partner_id,
        "company_is_new": True,
        "debug_trace": {
            **debug_trace,
            "matched_company": None,
            "company_resolution": "created",
            "created_company_name": final_company_name,
            "final_partner_id": partner_id,
        },
        "normalized_ticket": normalized,
    }


def resolve_ticket_fields_node(
    state: TicketAgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    if state.get("error"):
        return {}

    deps = _get_deps(config)
    odoo = deps.odoo_service._wrapper
    normalized = state["normalized_ticket"]

    raw_team = normalized.get("team") or state.get("team_name")
    raw_type = normalized.get("ticket_type")
    raw_category = normalized.get("category")
    raw_stage = normalized.get("stage")
    raw_tags = normalized.get("tags") or []
    raw_priority = normalized.get("priority")

    normalized_type = normalize_ticket_type(raw_type or "")
    normalized_priority = normalize_priority(raw_priority or "")
    missing_fields = list(state.get("missing_fields", []))

    if state.get("company_is_new"):
        raw_tags = list(raw_tags) + ["Cliente nuevo"]
    if missing_fields:
        raw_tags = list(raw_tags) + ["Faltan datos"]
    ticket_defaults = _build_ticket_defaults(
        normalized_type=normalized_type,
        raw_team=raw_team,
        raw_category=raw_category,
        raw_tags=raw_tags,
        normalized_priority=normalized_priority,
    )

    odoo_type_name = CANONICAL_TYPE_TO_ODOO_NAME.get(
        normalized_type,
        ticket_defaults["ticket_type_name"],
    )

    team_id = _find_id_by_name(odoo, Table.TicketTeam, ticket_defaults["team_name"])
    type_id = _find_id_by_name(odoo, Table.TicketType, odoo_type_name)
    category_id = _find_id_by_name(odoo, Table.TicketCategory, ticket_defaults["category_name"])
    stage_id = _find_id_by_name(odoo, Table.TicketStage, raw_stage)
    tag_ids = _find_tag_ids(odoo, ticket_defaults["tag_names"])

    return {
        "missing_fields": missing_fields,
        "resolved_fields": {
            "team_id": team_id,
            "type_id": type_id,
            "category_id": category_id,
            "stage_id": stage_id,
            "tag_ids": tag_ids,
            "team_name": ticket_defaults["team_name"],
            "ticket_type_name": odoo_type_name,
            "category_name": ticket_defaults["category_name"],
            "tag_names": ticket_defaults["tag_names"],
            "priority": ticket_defaults["priority"],
            "ticket_type_normalized": normalized_type,
            "priority_normalized": normalized_priority,
        }
    }


def create_ticket_node(
    state: TicketAgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    if state.get("error"):
        return {}

    deps = _get_deps(config)
    odoo = deps.odoo_service._wrapper
    normalized = state["normalized_ticket"]
    resolved = state.get("resolved_fields", {})
    missing_fields = state.get("missing_fields", [])

    existing_ticket_fields = _get_ticket_field_names(odoo)

    ticket_vals: dict[str, Any] = {}

    if "name" in existing_ticket_fields:
        ticket_vals["name"] = normalized["title"]

    if "description" in existing_ticket_fields:
        description = normalized["description"]
        if missing_fields:
            description += (
                "\n\nDatos que faltan:\n- "
                + "\n- ".join(missing_fields)
            )
        ticket_vals["description"] = description

    if "priority" in existing_ticket_fields:
        ticket_vals["priority"] = resolved.get("priority", "1")

    if state.get("partner_id") and "partner_id" in existing_ticket_fields:
        ticket_vals["partner_id"] = state["partner_id"]

    customer_email = normalized.get("customer_email")
    if customer_email and "partner_email" in existing_ticket_fields:
        ticket_vals["partner_email"] = customer_email

    partner_name = normalized.get("partner_name")
    if partner_name and "partner_name" in existing_ticket_fields:
        ticket_vals["partner_name"] = partner_name

    if resolved.get("team_id") and "team_id" in existing_ticket_fields:
        ticket_vals["team_id"] = resolved["team_id"]

    if resolved.get("type_id") and "type_id" in existing_ticket_fields:
        ticket_vals["type_id"] = resolved["type_id"]

    if resolved.get("category_id") and "category_id" in existing_ticket_fields:
        ticket_vals["category_id"] = resolved["category_id"]

    if resolved.get("stage_id") and "stage_id" in existing_ticket_fields:
        ticket_vals["stage_id"] = resolved["stage_id"]

    if resolved.get("tag_ids") and "tag_ids" in existing_ticket_fields:
        ticket_vals["tag_ids"] = [(6, 0, resolved["tag_ids"])]

    if not ticket_vals.get("name"):
        return {"error": "No se pudo construir el ticket: falta el campo name"}

    ticket_id = odoo._query(Table.Ticket, "create", [ticket_vals])
    return {
        "ticket_id": ticket_id,
        "ticket_vals": ticket_vals,
    }
