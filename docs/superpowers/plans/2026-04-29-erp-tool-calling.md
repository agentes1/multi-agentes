# ERP Tool-Calling Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar a los agentes LangGraph acceso a datos reales de Odoo via LangChain tool-calling para que respondan con información enriquecida del ERP sin comprometer la fiabilidad de las operaciones de escritura.

**Architecture:** Nueva capa `OdooService` centraliza todos los métodos de dominio sobre `OdooAPIWrapper`. Factory `build_odoo_tools(service)` genera 9 LangChain tools de solo lectura. Nuevo `enrich_context_node` en cada agente ejecuta tool-calling antes de los nodos de mutación.

**Tech Stack:** Python 3.11+, LangChain Core (`@tool`, `bind_tools`, `ToolMessage`, `HumanMessage`), LangGraph, `xmlrpc.client`, pytest, `unittest.mock.MagicMock`

**Entorno:**
- Venv: `C:\Users\keess\Desktop\Proy_4\.venv\Scripts\python.exe`
- PYTHONPATH: `C:\Users\keess\Desktop\Proy_4\multi-agentes`
- Todos los comandos se ejecutan desde `C:\Users\keess\Desktop\Proy_4`

---

## File Map

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `odoo/helpers.py` | Modificar | Fix typo `jelpdesk.ticket` → `helpdesk.ticket` |
| `odoo/service.py` | Crear | `OdooService`: métodos de dominio (consultas + mutaciones) sobre `OdooAPIWrapper` |
| `odoo/tools.py` | Crear | `build_odoo_tools(service)` → 9 `@tool` de solo lectura |
| `tests/test_odoo_service.py` | Crear | Tests de integración para `OdooService` (requieren Odoo corriendo) |
| `tests/test_odoo_tools.py` | Crear | Tests unitarios con `OdooService` mockeado (sin Odoo) |
| `agents/budget_agent/dependencies.py` | Modificar | `BudgetDependencies` usa `OdooService` + `llm` |
| `agents/budget_agent/state.py` | Modificar | +`odoo_context: dict` |
| `agents/budget_agent/nodes.py` | Modificar | Renombrar `odoo_wrapper→odoo_service`, añadir `enrich_context_node` |
| `agents/budget_agent/graph.py` | Modificar | +`enrich_context_node` antes de `prepare_budget_node` |
| `agents/intake_agent/dependencies.py` | Modificar | `TicketAgentDependencies` usa `OdooService` |
| `agents/intake_agent/state.py` | Modificar | +`odoo_context: dict` |
| `agents/intake_agent/nodes.py` | Modificar | Añadir `enrich_context_node` |
| `agents/intake_agent/graph.py` | Modificar | +`enrich_context` entre `normalize_email` y `ensure_partner` |

---

## Task 1: Fix typo en helpers.py

**Files:**
- Modify: `multi-agentes/odoo/helpers.py:6`

- [ ] **Step 1: Aplicar el fix**

En `multi-agentes/odoo/helpers.py`, línea 6, cambiar:

```python
Ticket = 'jelpdesk.ticket'
```

por:

```python
Ticket = 'helpdesk.ticket'
```

- [ ] **Step 2: Verificar que no queda ninguna referencia al typo**

```bash
grep -r "jelpdesk" /c/Users/keess/Desktop/Proy_4/multi-agentes/
```

Expected: ningún output.

- [ ] **Step 3: Commit**

```bash
cd /c/Users/keess/Desktop/Proy_4/multi-agentes && git add odoo/helpers.py && git commit -m "fix: corrige typo helpdesk.ticket en Table enum"
```

---

## Task 2: Crear OdooService

**Files:**
- Create: `multi-agentes/odoo/service.py`
- Create: `multi-agentes/tests/test_odoo_service.py`

- [ ] **Step 1: Escribir los tests de integración (RED) — requieren Odoo corriendo**

Crear `multi-agentes/tests/test_odoo_service.py`:

```python
import pytest
from odoo.service import OdooService
from odoo.api import OdooAPIWrapper
from odoo.helpers import Table
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD


@pytest.fixture(scope="module")
def service():
    wrapper = OdooAPIWrapper(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)
    return OdooService(wrapper)


# ── MUTACIONES ──────────────────────────────────────────────────────────────

def test_find_products_by_text_returns_list(service):
    results = service.find_products_by_text("CRM", limit=5)
    assert isinstance(results, list)
    for p in results:
        assert "id" in p
        assert "name" in p


def test_get_or_create_contact_creates_new(service):
    name = "_test_empresa_temp_borrar"
    partner_id = service.get_or_create_contact(name)
    assert isinstance(partner_id, int)
    service._wrapper.delete(Table.Contact, [partner_id])


def test_get_or_create_contact_returns_existing_id(service):
    name = "_test_empresa_dedup"
    pid1 = service.get_or_create_contact(name)
    pid2 = service.get_or_create_contact(name)
    assert pid1 == pid2
    service._wrapper.delete(Table.Contact, [pid1])


def test_create_and_get_sale_order(service):
    partner_id = service.get_or_create_contact("_test_cliente_orden_temp")
    order_id = service.create_sale_order(partner_id)
    assert isinstance(order_id, int)
    order = service.get_sale_order(order_id)
    assert "amount_total" in order
    # cancelar la orden antes de borrar el cliente
    service._wrapper._query("sale.order", "action_cancel", [[order_id]])
    service._wrapper.delete(Table.Contact, [partner_id])


# ── CONSULTAS ────────────────────────────────────────────────────────────────

def test_search_products_returns_list(service):
    results = service.search_products("CRM")
    assert isinstance(results, list)


def test_get_product_by_code_returns_none_for_invalid(service):
    result = service.get_product_by_code("CODIGO_INEXISTENTE_XYZ")
    assert result is None


def test_list_catalog_returns_list(service):
    results = service.list_catalog()
    assert isinstance(results, list)


def test_find_client_returns_none_for_unknown(service):
    result = service.find_client("Empresa Que No Existe XYZ 9999")
    assert result is None


def test_list_client_orders_returns_list(service):
    results = service.list_client_orders(partner_id=1, limit=5)
    assert isinstance(results, list)


def test_list_client_tickets_returns_list(service):
    results = service.list_client_tickets(partner_id=1, limit=5)
    assert isinstance(results, list)
```

- [ ] **Step 2: Ejecutar — debe fallar con ImportError**

```bash
cd /c/Users/keess/Desktop/Proy_4 && .venv/Scripts/python.exe -m pytest multi-agentes/tests/test_odoo_service.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'OdooService' from 'odoo.service'`

- [ ] **Step 3: Implementar OdooService**

Crear `multi-agentes/odoo/service.py`:

```python
from __future__ import annotations

from odoo.api import OdooAPIWrapper
from odoo.helpers import Table


class OdooService:
    """Capa de dominio sobre OdooAPIWrapper.

    Separa explícitamente consultas (expuestas como LangChain tools en odoo/tools.py)
    de mutaciones (usadas por nodos hardcodeados del grafo).
    """

    def __init__(self, wrapper: OdooAPIWrapper) -> None:
        self._wrapper = wrapper

    # ─── MUTACIONES ────────────────────────────────────────────────────────────
    # Usadas directamente por nodos del grafo. NO expuestas como tools.
    # Razón: crear registros en Odoo debe ser determinista, no delegarse al LLM.

    def find_products_by_text(self, text: str, limit: int = 5) -> list[dict]:
        domain = [("name", "ilike", text), ("active", "=", True)]
        return self._wrapper._query(
            "product.product",
            "search_read",
            [domain],
            {"fields": ["id", "name", "default_code", "list_price"], "limit": limit},
        ) or []

    def get_or_create_contact(self, company_name: str) -> int:
        existing = self._wrapper.get_by_value(
            Table.Contact,
            {"name": company_name},
            fields=["id"],
            limit=1,
        )
        if existing:
            return existing[0]["id"]
        return self._wrapper._query(
            "res.partner",
            "create",
            [{"name": company_name, "is_company": True, "customer_rank": 1}],
        )

    def create_sale_order(self, partner_id: int) -> int:
        return self._wrapper._query(
            "sale.order",
            "create",
            [{"partner_id": partner_id}],
        )

    def create_sale_order_line(
        self, order_id: int, product_id: int, quantity: int
    ) -> int:
        return self._wrapper._query(
            "sale.order.line",
            "create",
            [{
                "order_id": order_id,
                "product_id": product_id,
                "product_uom_qty": quantity,
            }],
        )

    def get_sale_order(self, sale_order_id: int) -> dict:
        results = self._wrapper._query(
            "sale.order",
            "read",
            [[sale_order_id]],
            {"fields": ["name", "partner_id", "amount_untaxed", "amount_total", "state"]},
        )
        return results[0] if results else {}

    def create_helpdesk_ticket(
        self,
        name: str,
        description: str,
        partner_id: int | None = None,
        partner_email: str | None = None,
        team_id: int | None = None,
    ) -> int:
        vals: dict = {"name": name, "description": description}
        if partner_id:
            vals["partner_id"] = partner_id
        if partner_email:
            vals["partner_email"] = partner_email
        if team_id:
            vals["team_id"] = team_id
        return self._wrapper._query("helpdesk.ticket", "create", [vals])

    # ─── CONSULTAS ─────────────────────────────────────────────────────────────
    # Expuestas como LangChain tools en odoo/tools.py.
    # Solo lectura — si fallan, no modifican nada en Odoo.

    def search_products(self, text: str, limit: int = 10) -> list[dict]:
        domain = [("name", "ilike", text), ("active", "=", True)]
        return self._wrapper._query(
            "product.product",
            "search_read",
            [domain],
            {"fields": ["id", "name", "default_code", "list_price", "type"], "limit": limit},
        ) or []

    def get_product_by_code(self, code: str) -> dict | None:
        results = self._wrapper._query(
            "product.product",
            "search_read",
            [[("default_code", "=", code), ("active", "=", True)]],
            {"fields": ["id", "name", "default_code", "list_price", "type"], "limit": 1},
        )
        return results[0] if results else None

    def list_catalog(self) -> list[dict]:
        return self._wrapper._query(
            "product.product",
            "search_read",
            [[("active", "=", True)]],
            {"fields": ["id", "name", "default_code", "list_price"], "limit": 100},
        ) or []

    def find_client(self, name: str) -> dict | None:
        results = self._wrapper._query(
            "res.partner",
            "search_read",
            [[("name", "ilike", name), ("active", "=", True)]],
            {"fields": ["id", "name", "email", "phone", "is_company"], "limit": 1},
        )
        return results[0] if results else None

    def get_client_history(self, partner_id: int) -> dict:
        return {
            "orders": self.list_client_orders(partner_id),
            "tickets": self.list_client_tickets(partner_id),
        }

    def get_order(self, order_id: int) -> dict:
        results = self._wrapper._query(
            "sale.order",
            "read",
            [[order_id]],
            {"fields": ["name", "state", "amount_untaxed", "amount_total", "date_order"]},
        )
        return results[0] if results else {}

    def list_client_orders(self, partner_id: int, limit: int = 10) -> list[dict]:
        return self._wrapper._query(
            "sale.order",
            "search_read",
            [[("partner_id", "=", partner_id)]],
            {
                "fields": ["id", "name", "state", "amount_total", "date_order"],
                "limit": limit,
                "order": "date_order desc",
            },
        ) or []

    def get_ticket(self, ticket_id: int) -> dict:
        results = self._wrapper._query(
            "helpdesk.ticket",
            "read",
            [[ticket_id]],
            {"fields": ["name", "description", "stage_id", "team_id", "partner_id"]},
        )
        return results[0] if results else {}

    def list_client_tickets(self, partner_id: int, limit: int = 10) -> list[dict]:
        return self._wrapper._query(
            "helpdesk.ticket",
            "search_read",
            [[("partner_id", "=", partner_id)]],
            {
                "fields": ["id", "name", "stage_id", "team_id"],
                "limit": limit,
                "order": "id desc",
            },
        ) or []
```

- [ ] **Step 4: Ejecutar tests — deben pasar (Odoo debe estar corriendo)**

```bash
cd /c/Users/keess/Desktop/Proy_4 && .venv/Scripts/python.exe -m pytest multi-agentes/tests/test_odoo_service.py -v
```

Expected: todos PASS.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/keess/Desktop/Proy_4/multi-agentes && git add odoo/service.py tests/test_odoo_service.py && git commit -m "feat: añade OdooService con métodos de dominio y consultas sobre OdooAPIWrapper"
```

---

## Task 3: Crear odoo/tools.py

**Files:**
- Create: `multi-agentes/odoo/tools.py`
- Create: `multi-agentes/tests/test_odoo_tools.py`

- [ ] **Step 1: Escribir los tests unitarios (RED) — no requieren Odoo**

Crear `multi-agentes/tests/test_odoo_tools.py`:

```python
from unittest.mock import MagicMock
from odoo.tools import build_odoo_tools
from odoo.service import OdooService


def _make_tools():
    mock_service = MagicMock(spec=OdooService)
    tools = build_odoo_tools(mock_service)
    return {t.name: t for t in tools}, mock_service


def test_build_odoo_tools_returns_nine_tools():
    tool_map, _ = _make_tools()
    assert len(tool_map) == 9


def test_buscar_productos_llama_a_search_products():
    tool_map, mock_service = _make_tools()
    mock_service.search_products.return_value = [{"id": 1, "name": "CRM Base"}]
    result = tool_map["buscar_productos"].invoke({"texto": "CRM"})
    assert result == [{"id": 1, "name": "CRM Base"}]
    mock_service.search_products.assert_called_once_with("CRM")


def test_obtener_producto_devuelve_dict_vacio_si_no_existe():
    tool_map, mock_service = _make_tools()
    mock_service.get_product_by_code.return_value = None
    result = tool_map["obtener_producto"].invoke({"codigo": "INEXISTENTE"})
    assert result == {}


def test_listar_catalogo_llama_a_list_catalog():
    tool_map, mock_service = _make_tools()
    mock_service.list_catalog.return_value = [{"id": 1, "name": "P1"}]
    result = tool_map["listar_catalogo"].invoke({})
    assert len(result) == 1
    mock_service.list_catalog.assert_called_once()


def test_buscar_cliente_devuelve_dict_vacio_si_no_existe():
    tool_map, mock_service = _make_tools()
    mock_service.find_client.return_value = None
    result = tool_map["buscar_cliente"].invoke({"nombre": "ACME"})
    assert result == {}


def test_historial_cliente_devuelve_not_found_si_no_hay_cliente():
    tool_map, mock_service = _make_tools()
    mock_service.find_client.return_value = None
    result = tool_map["historial_cliente"].invoke({"nombre": "Desconocido"})
    assert result == {"orders": [], "tickets": [], "found": False}
    mock_service.get_client_history.assert_not_called()


def test_historial_cliente_devuelve_historial_si_cliente_existe():
    tool_map, mock_service = _make_tools()
    mock_service.find_client.return_value = {"id": 42, "name": "ACME"}
    mock_service.get_client_history.return_value = {"orders": [{"id": 1}], "tickets": []}
    result = tool_map["historial_cliente"].invoke({"nombre": "ACME"})
    assert result["found"] is True
    assert len(result["orders"]) == 1
    mock_service.get_client_history.assert_called_once_with(42)


def test_listar_ordenes_cliente_devuelve_lista_vacia_si_no_hay_cliente():
    tool_map, mock_service = _make_tools()
    mock_service.find_client.return_value = None
    result = tool_map["listar_ordenes_cliente"].invoke({"nombre": "Nadie"})
    assert result == []
    mock_service.list_client_orders.assert_not_called()


def test_listar_tickets_cliente_devuelve_lista_vacia_si_no_hay_cliente():
    tool_map, mock_service = _make_tools()
    mock_service.find_client.return_value = None
    result = tool_map["listar_tickets_cliente"].invoke({"nombre": "Nadie"})
    assert result == []
    mock_service.list_client_tickets.assert_not_called()
```

- [ ] **Step 2: Ejecutar — debe fallar con ImportError**

```bash
cd /c/Users/keess/Desktop/Proy_4 && .venv/Scripts/python.exe -m pytest multi-agentes/tests/test_odoo_tools.py -v 2>&1 | head -15
```

Expected: `ImportError: cannot import name 'build_odoo_tools' from 'odoo.tools'`

- [ ] **Step 3: Implementar odoo/tools.py**

Crear `multi-agentes/odoo/tools.py`:

```python
from langchain_core.tools import tool

from odoo.service import OdooService


def build_odoo_tools(service: OdooService) -> list:
    """Fábrica de LangChain tools de solo lectura sobre OdooService.

    TOOL-CALLING — solo lectura.
    El LLM decide cuándo y qué consultar según el contexto de la conversación.
    Si una tool falla, no modifica nada en Odoo.

    MUTACIONES — nodos hardcodeados del grafo (NO aquí).
    Razón: crear tickets, órdenes y contactos debe ser determinista.
    Un LLM que alucina no puede crear registros en producción de forma autónoma.
    """

    @tool
    def buscar_productos(texto: str) -> list:
        """Busca productos en el catálogo de Odoo por nombre o descripción."""
        return service.search_products(texto)

    @tool
    def obtener_producto(codigo: str) -> dict:
        """Obtiene detalles y precio de un producto por su código interno (default_code)."""
        return service.get_product_by_code(codigo) or {}

    @tool
    def listar_catalogo() -> list:
        """Devuelve todos los productos disponibles en Odoo con nombre, código y precio."""
        return service.list_catalog()

    @tool
    def buscar_cliente(nombre: str) -> dict:
        """Comprueba si existe un cliente en Odoo por nombre. Devuelve sus datos o dict vacío."""
        return service.find_client(nombre) or {}

    @tool
    def historial_cliente(nombre: str) -> dict:
        """Devuelve las órdenes de venta anteriores y los tickets del cliente en Odoo."""
        client = service.find_client(nombre)
        if not client:
            return {"orders": [], "tickets": [], "found": False}
        history = service.get_client_history(client["id"])
        history["found"] = True
        return history

    @tool
    def consultar_orden(order_id: int) -> dict:
        """Obtiene el estado y total de una orden de venta por ID."""
        return service.get_order(order_id)

    @tool
    def listar_ordenes_cliente(nombre: str) -> list:
        """Devuelve todas las órdenes de venta de un cliente buscando por nombre."""
        client = service.find_client(nombre)
        if not client:
            return []
        return service.list_client_orders(client["id"])

    @tool
    def consultar_ticket(ticket_id: int) -> dict:
        """Obtiene el estado y descripción de un ticket de soporte por ID."""
        return service.get_ticket(ticket_id)

    @tool
    def listar_tickets_cliente(nombre: str) -> list:
        """Devuelve todos los tickets de soporte de un cliente buscando por nombre."""
        client = service.find_client(nombre)
        if not client:
            return []
        return service.list_client_tickets(client["id"])

    return [
        buscar_productos,
        obtener_producto,
        listar_catalogo,
        buscar_cliente,
        historial_cliente,
        consultar_orden,
        listar_ordenes_cliente,
        consultar_ticket,
        listar_tickets_cliente,
    ]
```

- [ ] **Step 4: Ejecutar tests — deben pasar**

```bash
cd /c/Users/keess/Desktop/Proy_4 && .venv/Scripts/python.exe -m pytest multi-agentes/tests/test_odoo_tools.py -v
```

Expected: 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/keess/Desktop/Proy_4/multi-agentes && git add odoo/tools.py tests/test_odoo_tools.py && git commit -m "feat: añade build_odoo_tools() con 9 LangChain tools de solo lectura sobre Odoo"
```

---

## Task 4: Actualizar budget_agent

**Files:**
- Modify: `multi-agentes/agents/budget_agent/dependencies.py`
- Modify: `multi-agentes/agents/budget_agent/state.py`
- Modify: `multi-agentes/agents/budget_agent/nodes.py`
- Modify: `multi-agentes/agents/budget_agent/graph.py`

- [ ] **Step 1: Reemplazar dependencies.py**

Reemplazar el contenido completo de `multi-agentes/agents/budget_agent/dependencies.py`:

```python
from dataclasses import dataclass
from typing import Any

from odoo.api import OdooAPIWrapper
from odoo.service import OdooService
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_PASSWORD, ODOO_USERNAME
from shared.llm import get_llm


@dataclass
class BudgetDependencies:
    llm: Any
    odoo_service: OdooService


def build_budget_dependencies() -> BudgetDependencies:
    wrapper = OdooAPIWrapper(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)
    return BudgetDependencies(
        llm=get_llm(),
        odoo_service=OdooService(wrapper),
    )
```

- [ ] **Step 2: Actualizar state.py — añadir odoo_context**

Reemplazar el contenido completo de `multi-agentes/agents/budget_agent/state.py`:

```python
from typing import Any, TypedDict

from langchain_core.messages import BaseMessage


class BudgetState(TypedDict, total=False):
    messages: list[BaseMessage]

    # json ya normalizado por el agente anterior
    normalized_request: dict[str, Any]
    # contexto enriquecido por enrich_context_node via tool-calling (solo lectura)
    odoo_context: dict[str, Any]
    # productos seleccionados a partir de los requisitos
    selected_products: list[str]
    # id del contacto/cliente en odoo
    partner_id: int
    # id del presupuesto creado en odoo
    sale_order_id: int
    # resumen simple del presupuesto creado
    quote_summary: dict[str, Any]

    # error si algo falla durante el flujo
    error: str
```

- [ ] **Step 3: Reemplazar nodes.py completo**

Reemplazar el contenido completo de `multi-agentes/agents/budget_agent/nodes.py`:

```python
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from agents.budget_agent.dependencies import BudgetDependencies
from agents.budget_agent.state import BudgetState
from odoo.tools import build_odoo_tools


def _get_deps(config: RunnableConfig) -> BudgetDependencies:
    deps = config.get("configurable", {}).get("deps")
    if deps is None:
        raise RuntimeError("BudgetDependencies no inyectadas en config")
    return deps


async def _run_tool_calls(response, tools: list) -> list[ToolMessage]:
    tool_map = {t.name: t for t in tools}
    results = []
    for tc in getattr(response, "tool_calls", []):
        tool = tool_map.get(tc["name"])
        if tool:
            try:
                output = tool.invoke(tc["args"])
                results.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))
            except Exception as e:
                results.append(ToolMessage(content=f"Error: {e}", tool_call_id=tc["id"]))
    return results


# TOOL-CALLING: el LLM consulta Odoo para enriquecer el contexto del presupuesto.
# Solo lectura — los errores son silenciosos para no bloquear el flujo principal.
# Las mutaciones (buscar productos, crear partner, crear orden) ocurren en nodos siguientes.
async def enrich_context_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)
    tools = build_odoo_tools(deps.odoo_service)
    llm_with_tools = deps.llm.bind_tools(tools)

    normalized = state.get("normalized_request", {})
    company_name = normalized.get("company_name", "")
    requirements = normalized.get("requirements", [])

    prompt = (
        f"Consulta el catálogo de Odoo y el historial del cliente para preparar el presupuesto. "
        f"Empresa: '{company_name}'. Requisitos solicitados: {requirements}."
    )
    messages = list(state.get("messages", [])) + [HumanMessage(content=prompt)]

    try:
        response = await llm_with_tools.ainvoke(messages)
        tool_messages = await _run_tool_calls(response, tools)
        return {
            "messages": messages + [response] + tool_messages,
            "odoo_context": {"raw_results": [m.content for m in tool_messages]},
        }
    except Exception:
        return {"odoo_context": {}}


async def prepare_budget_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)

    normalized_request = state["normalized_request"]
    requirements = normalized_request.get("requirements", [])

    if not requirements:
        return {
            "error": "La solicitud no contiene requisitos. No se puede crear presupuesto.",
            "selected_products": [],
        }

    selected_products = []
    unmatched_requirements = []

    try:
        for requirement in requirements:
            value = str(requirement).strip()
            if not value:
                continue

            matches = deps.odoo_service.find_products_by_text(value, limit=5)

            if matches:
                product = matches[0]
                if not any(p["id"] == product["id"] for p in selected_products):
                    selected_products.append(product)
            else:
                unmatched_requirements.append(value)

    except Exception as e:
        return {
            "error": f"Error al consultar productos en Odoo: {e}",
            "selected_products": [],
        }

    if not selected_products:
        return {
            "error": f"No se encontraron productos en Odoo para los requisitos: {requirements}",
            "selected_products": [],
        }

    return {
        "messages": [
            AIMessage(
                content=f"Solicitud preparada para presupuesto con {len(selected_products)} productos encontrados en Odoo"
            )
        ],
        "selected_products": selected_products,
        "unmatched_requirements": unmatched_requirements,
        "error": None,
    }


async def ensure_partner_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)

    normalized_request = state["normalized_request"]
    company_name = normalized_request.get("company_name", "Desconocido")

    try:
        partner_id = deps.odoo_service.get_or_create_contact(company_name)
    except Exception as e:
        return {"error": f"Error al obtener o crear el contacto en Odoo: {e}"}

    return {
        "messages": [
            AIMessage(content=f"Contacto preparado en Odoo para {company_name} con id {partner_id}")
        ],
        "partner_id": partner_id,
        "error": None,
    }


async def create_odoo_quote_node(state: BudgetState, config: RunnableConfig) -> dict:
    deps = _get_deps(config)

    normalized_request = state["normalized_request"]
    company_name = normalized_request.get("company_name", "Desconocido")
    selected_products = state.get("selected_products", [])
    partner_id = state["partner_id"]

    try:
        sale_order_id = deps.odoo_service.create_sale_order(partner_id=partner_id)

        for product in selected_products:
            deps.odoo_service.create_sale_order_line(
                order_id=sale_order_id,
                product_id=product["id"],
                quantity=1,
            )

        order = deps.odoo_service.get_sale_order(sale_order_id)

    except Exception as e:
        return {"error": f"Error al crear el presupuesto en Odoo: {e}"}

    quote_summary = {
        "company_name": company_name,
        "sale_order_id": sale_order_id,
        "selected_products": [
            {
                "id": product["id"],
                "name": product.get("name", ""),
                "default_code": product.get("default_code", ""),
            }
            for product in selected_products
        ],
        "subtotal": float(order.get("amount_untaxed", 0)),
        "total": float(order.get("amount_total", 0)),
        "currency": "EUR",
    }

    return {
        "messages": [
            AIMessage(
                content=f"Presupuesto creado en Odoo para {company_name}. ID={sale_order_id}, total={quote_summary['total']} EUR"
            )
        ],
        "sale_order_id": sale_order_id,
        "quote_summary": quote_summary,
        "error": None,
    }


async def error_node(state: BudgetState) -> dict:
    error_msg = state.get("error", "Error desconocido en el agente de presupuestos")
    return {
        "messages": [AIMessage(content=f"No se ha podido crear el presupuesto: {error_msg}")]
    }
```

- [ ] **Step 4: Reemplazar graph.py — añadir enrich_context_node**

Reemplazar el contenido completo de `multi-agentes/agents/budget_agent/graph.py`:

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agents.budget_agent.nodes import (
    enrich_context_node,
    error_node,
    prepare_budget_node,
    ensure_partner_node,
    create_odoo_quote_node,
)
from agents.budget_agent.state import BudgetState


def _route_after_enrich(state: BudgetState) -> str:
    return "error_node" if state.get("error") else "prepare_budget_node"


def _route_after_prepare(state: BudgetState) -> str:
    return "error_node" if state.get("error") else "ensure_partner_node"


def _route_after_partner(state: BudgetState) -> str:
    return "error_node" if state.get("error") else "create_odoo_quote_node"


def build_budget_graph():
    builder = StateGraph(BudgetState)

    builder.add_node("enrich_context_node", enrich_context_node)
    builder.add_node("prepare_budget_node", prepare_budget_node)
    builder.add_node("ensure_partner_node", ensure_partner_node)
    builder.add_node("create_odoo_quote_node", create_odoo_quote_node)
    builder.add_node("error_node", error_node)

    builder.add_edge(START, "enrich_context_node")
    builder.add_conditional_edges("enrich_context_node", _route_after_enrich)
    builder.add_conditional_edges("prepare_budget_node", _route_after_prepare)
    builder.add_conditional_edges("ensure_partner_node", _route_after_partner)
    builder.add_edge("create_odoo_quote_node", END)
    builder.add_edge("error_node", END)

    return builder.compile(checkpointer=InMemorySaver())
```

- [ ] **Step 5: Verificar que el agente importa sin errores**

```bash
cd /c/Users/keess/Desktop/Proy_4 && .venv/Scripts/python.exe -c "from agents.budget_agent.graph import build_budget_graph; g = build_budget_graph(); print('budget_agent OK')"
```

Expected: `budget_agent OK`

- [ ] **Step 6: Commit**

```bash
cd /c/Users/keess/Desktop/Proy_4/multi-agentes && git add agents/budget_agent/ && git commit -m "feat: budget_agent usa OdooService y añade enrich_context_node con tool-calling"
```

---

## Task 5: Actualizar intake_agent

**Files:**
- Modify: `multi-agentes/agents/intake_agent/dependencies.py`
- Modify: `multi-agentes/agents/intake_agent/state.py`
- Modify: `multi-agentes/agents/intake_agent/nodes.py`
- Modify: `multi-agentes/agents/intake_agent/graph.py`

- [ ] **Step 1: Reemplazar dependencies.py**

Reemplazar el contenido completo de `multi-agentes/agents/intake_agent/dependencies.py`:

```python
from dataclasses import dataclass
from typing import Any

from shared.llm import get_llm
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD
from odoo.api import OdooAPIWrapper
from odoo.service import OdooService


@dataclass
class TicketAgentDependencies:
    llm: Any
    odoo_service: OdooService


def build_ticket_dependencies() -> TicketAgentDependencies:
    wrapper = OdooAPIWrapper(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)
    return TicketAgentDependencies(
        llm=get_llm(),
        odoo_service=OdooService(wrapper),
    )
```

- [ ] **Step 2: Actualizar state.py — añadir odoo_context**

Reemplazar el contenido completo de `multi-agentes/agents/intake_agent/state.py`:

```python
from typing import Any, TypedDict


class TicketAgentState(TypedDict, total=False):
    # Entrada
    email_subject: str
    email_body: str
    sender_email: str
    sender_name: str | None
    team_name: str | None

    # Salida de normalización
    normalized_ticket: dict[str, Any]

    # Contexto enriquecido por enrich_context_node via tool-calling (solo lectura)
    odoo_context: dict[str, Any]

    # Resultado Odoo
    partner_id: int | None
    ticket_id: int | None

    # Control simple
    error: str | None
```

- [ ] **Step 3: Añadir enrich_context_node a nodes.py**

Añadir al bloque de imports de `multi-agentes/agents/intake_agent/nodes.py` (después de los imports existentes):

```python
from langchain_core.messages import HumanMessage, ToolMessage
from odoo.tools import build_odoo_tools
```

Añadir las siguientes funciones DESPUÉS de `normalize_email_node` y ANTES de `ensure_partner_node`:

```python
async def _run_tool_calls(response, tools: list) -> list[ToolMessage]:
    tool_map = {t.name: t for t in tools}
    results = []
    for tc in getattr(response, "tool_calls", []):
        tool = tool_map.get(tc["name"])
        if tool:
            try:
                output = tool.invoke(tc["args"])
                results.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))
            except Exception as e:
                results.append(ToolMessage(content=f"Error: {e}", tool_call_id=tc["id"]))
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
    tools = build_odoo_tools(deps.odoo_service)
    llm_with_tools = deps.llm.bind_tools(tools)

    normalized = state.get("normalized_ticket", {})
    customer_name = normalized.get("customer_name") or ""
    customer_email = normalized.get("customer_email") or ""

    prompt = (
        f"Consulta si el cliente existe en Odoo y obtén su historial. "
        f"Nombre: '{customer_name}', email: '{customer_email}'."
    )

    try:
        response = await llm_with_tools.ainvoke([HumanMessage(content=prompt)])
        tool_messages = await _run_tool_calls(response, tools)
        return {"odoo_context": {"raw_results": [m.content for m in tool_messages]}}
    except Exception:
        return {"odoo_context": {}}
```

- [ ] **Step 4: Actualizar graph.py — añadir enrich_context entre normalize y ensure_partner**

Reemplazar el contenido completo de `multi-agentes/agents/intake_agent/graph.py`:

```python
from langgraph.graph import START, END, StateGraph

from .state import TicketAgentState
from .nodes import (
    normalize_email_node,
    enrich_context_node,
    ensure_partner_node,
    create_ticket_node,
)


def build_ticket_graph():
    graph = StateGraph(TicketAgentState)

    graph.add_node("normalize_email", normalize_email_node)
    graph.add_node("enrich_context", enrich_context_node)
    graph.add_node("ensure_partner", ensure_partner_node)
    graph.add_node("create_ticket", create_ticket_node)

    graph.add_edge(START, "normalize_email")
    graph.add_edge("normalize_email", "enrich_context")
    graph.add_edge("enrich_context", "ensure_partner")
    graph.add_edge("ensure_partner", "create_ticket")
    graph.add_edge("create_ticket", END)

    return graph.compile()
```

- [ ] **Step 5: Verificar que el agente importa sin errores**

```bash
cd /c/Users/keess/Desktop/Proy_4 && .venv/Scripts/python.exe -c "from agents.intake_agent.graph import build_ticket_graph; g = build_ticket_graph(); print('intake_agent OK')"
```

Expected: `intake_agent OK`

- [ ] **Step 6: Commit**

```bash
cd /c/Users/keess/Desktop/Proy_4/multi-agentes && git add agents/intake_agent/ && git commit -m "feat: intake_agent usa OdooService y añade enrich_context_node con tool-calling"
```

---

## Task 6: Verificación final

**Files:** ninguno nuevo — verificación del sistema completo.

- [ ] **Step 1: Ejecutar todos los tests unitarios (sin Odoo)**

```bash
cd /c/Users/keess/Desktop/Proy_4 && .venv/Scripts/python.exe -m pytest multi-agentes/tests/test_odoo_tools.py -v
```

Expected: 9 tests PASS.

- [ ] **Step 2: Verificar que ambos grafos compilan**

```bash
cd /c/Users/keess/Desktop/Proy_4 && .venv/Scripts/python.exe -c "
from agents.budget_agent.graph import build_budget_graph
from agents.intake_agent.graph import build_ticket_graph
build_budget_graph()
build_ticket_graph()
print('Ambos grafos OK')
"
```

Expected: `Ambos grafos OK`

- [ ] **Step 3: Ejecutar tests de integración (requiere Odoo corriendo)**

Arrancar Odoo si no está corriendo:
```bash
cd /c/Users/keess/Desktop/Proy_4/multi-agentes/odoo && docker compose up -d
```

Esperar 30 segundos, luego:

```bash
cd /c/Users/keess/Desktop/Proy_4 && .venv/Scripts/python.exe -m pytest multi-agentes/tests/test_odoo_service.py -v
```

Expected: todos PASS.

- [ ] **Step 4: Verificar que el typo fix no rompe nada**

```bash
cd /c/Users/keess/Desktop/Proy_4 && .venv/Scripts/python.exe -c "from odoo.helpers import Table; assert Table.Ticket == 'helpdesk.ticket'; print('Table.Ticket OK')"
```

Expected: `Table.Ticket OK`

- [ ] **Step 5: Commit final si hay cambios pendientes**

```bash
cd /c/Users/keess/Desktop/Proy_4/multi-agentes && git status
```

Si hay archivos sin commitear, añadirlos y hacer commit final:

```bash
git add . && git commit -m "chore: verificación final ERP tool-calling integration"
```
