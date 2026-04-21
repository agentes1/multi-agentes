# Design: ERP Tool-Calling Integration (Opción B Híbrida)

**Date:** 2026-04-29
**Status:** Approved
**Author:** Diego

---

## Problema

Los agentes actuales (`intake_agent`, `budget_agent`) ejecutan flujos hardcodeados contra Odoo pero no pueden **responder con información de Odoo** de forma dinámica. Si el LLM necesita saber si un cliente ya existe, qué ha pedido antes, o qué tickets tiene abiertos, no tiene forma de consultarlo: actúa a ciegas.

## Objetivo

Dar a los agentes acceso a datos reales de Odoo mediante **LangChain tool-calling**, para que puedan responder con información enriquecida del ERP sin comprometer la fiabilidad de las operaciones de escritura.

---

## Decisión de arquitectura

### Principio central

| Tipo de operación                 | Quién la ejecuta            | Por qué                                             |
| ---------------------------------- | ---------------------------- | ---------------------------------------------------- |
| **Consultas** (solo lectura) | LLM via tool-calling         | Seguras: si falla, no cambia nada en Odoo            |
| **Mutaciones** (escritura)   | Nodos hardcodeados del grafo | Críticas: deben ser deterministas, sin alucinación |

### Por qué no MCP (Opción A)

El `odoo/mcp_server.py` existente tiene un bug de importación (`ODOO_URL` vs `ODOO_BASE_URL`) y solo expone 4 tools. Implementar sobre él requeriría fix + extensión, con overhead de proceso adicional. **Pendiente:** cuando la Opción B esté estable, exponer las mismas tools via MCP para reutilización externa (Claude Desktop, otros clientes).

---

## Archivos afectados

### Nuevos

| Archivo                      | Qué hace                                                                       |
| ---------------------------- | ------------------------------------------------------------------------------- |
| `odoo/service.py`          | `OdooService` — métodos de dominio de alto nivel sobre `OdooAPIWrapper`   |
| `odoo/tools.py`            | `build_odoo_tools(service)` — fábrica de `@tool` LangChain (solo lectura) |
| `tests/test_odoo_tools.py` | Tests unitarios con `OdooService` mockeado                                    |

### Modificados

| Archivo                                 | Cambio                                                    |
| --------------------------------------- | --------------------------------------------------------- |
| `odoo/helpers.py`                     | Fix typo:`'jelpdesk.ticket'` → `'helpdesk.ticket'`   |
| `agents/intake_agent/state.py`        | +campo `odoo_context: dict`                             |
| `agents/intake_agent/nodes.py`        | +`enrich_context_node`                                  |
| `agents/intake_agent/graph.py`        | +paso `enrich_context` entre normalize y ensure_partner |
| `agents/intake_agent/dependencies.py` | `odoo_service: OdooService` (antes `OdooAPIWrapper`)  |
| `agents/budget_agent/state.py`        | +campo `odoo_context: dict`                             |
| `agents/budget_agent/nodes.py`        | +`enrich_context_node`                                  |
| `agents/budget_agent/graph.py`        | +paso `enrich_context` antes de `prepare_budget`      |
| `agents/budget_agent/dependencies.py` | `odoo_service: OdooService` (antes `OdooAPIWrapper`)  |

---

## `odoo/service.py` — OdooService

Capa de dominio que envuelve `OdooAPIWrapper`. Separa explícitamente consultas de mutaciones via comentarios en el código.

### Métodos de consulta (expuestos como tools)

```python
search_products(text: str, limit: int = 10) -> list[dict]
    # Busca productos por nombre/descripción (fulltext en 'name')

get_product_by_code(code: str) -> dict | None
    # Obtiene detalles y precio de un producto por default_code

list_catalog() -> list[dict]
    # Devuelve todos los productos activos con nombre, código y precio

find_client(name: str) -> dict | None
    # Busca si existe un cliente por nombre (ilike) en res.partner

get_client_history(partner_id: int) -> dict
    # Devuelve órdenes anteriores + tickets del cliente
    # Retorna: {"orders": [...], "tickets": [...]}

get_order(order_id: int) -> dict
    # Estado, total y líneas de una orden de venta

list_client_orders(partner_id: int, limit: int = 10) -> list[dict]
    # Todas las órdenes de un cliente ordenadas por fecha

get_ticket(ticket_id: int) -> dict
    # Estado, descripción y equipo de un ticket

list_client_tickets(partner_id: int, limit: int = 10) -> list[dict]
    # Todos los tickets de un cliente
```

### Métodos de mutación (usados por nodos del grafo, NO expuestos como tools)

```python
find_products_by_text(text: str, limit: int = 5) -> list[dict]
    # Búsqueda interna para prepare_budget_node

get_or_create_contact(company_name: str) -> int
    # Crea el cliente en Odoo si no existe; devuelve partner_id

create_sale_order(partner_id: int) -> int
    # Crea cabecera de sale.order; devuelve sale_order_id

create_sale_order_line(order_id: int, product_id: int, quantity: int) -> int
    # Añade línea a la orden; devuelve line_id

get_sale_order(sale_order_id: int) -> dict
    # Lee la orden creada (amount_untaxed, amount_total)

create_helpdesk_ticket(**kwargs) -> int
    # Crea helpdesk.ticket; devuelve ticket_id
```

---

## `odoo/tools.py` — build_odoo_tools()

Fábrica que recibe un `OdooService` y devuelve lista de tools LangChain.

```python
# COMENTARIO QUE QUEDA EN EL CÓDIGO:
#
# TOOL-CALLING — solo lectura.
# El LLM decide cuándo y qué consultar según el contexto de la conversación.
# Si una tool falla, no modifica nada en Odoo.
#
# MUTACIONES — nodos hardcodeados del grafo (NO aquí).
# Razón: crear tickets, órdenes y contactos debe ser determinista.
# Un LLM que alucina no puede crear registros en producción de forma autónoma.

def build_odoo_tools(service: OdooService) -> list:
    ...
```

**Tools expuestas (9):**

| Tool                       | Parámetros        | Descripción para el LLM                               |
| -------------------------- | ------------------ | ------------------------------------------------------ |
| `buscar_productos`       | `texto: str`     | Busca productos en catálogo por nombre o descripción |
| `obtener_producto`       | `codigo: str`    | Detalles y precio de un producto por código interno   |
| `listar_catalogo`        | —                 | Todos los productos disponibles con precio             |
| `buscar_cliente`         | `nombre: str`    | Comprueba si existe un cliente en Odoo                 |
| `historial_cliente`      | `nombre: str`    | Órdenes anteriores y tickets de un cliente            |
| `consultar_orden`        | `order_id: int`  | Estado y total de una orden de venta                   |
| `listar_ordenes_cliente` | `nombre: str`    | Todas las órdenes de un cliente                       |
| `consultar_ticket`       | `ticket_id: int` | Estado y descripción de un ticket                     |
| `listar_tickets_cliente` | `nombre: str`    | Todos los tickets de un cliente                        |

---

## Nuevo nodo: `enrich_context_node`

Se añade a ambos agentes. Ejecuta un mini-loop de tool-calling antes de las mutaciones.

### Flujo intake_agent (actualizado)

```
START
  → normalize_email_node    (LLM: extrae título, descripción, datos del cliente)
  → enrich_context_node     (LLM + tools: consulta Odoo, enriquece contexto)
  → ensure_partner_node     (MUTACIÓN: crea/recupera partner)
  → create_ticket_node      (MUTACIÓN: crea helpdesk.ticket)
  → error_node              (terminal)
END
```

### Flujo budget_agent (actualizado)

```
START
  → enrich_context_node     (LLM + tools: consulta historial, productos similares)
  → prepare_budget_node     (busca productos en Odoo para los requisitos)
  → ensure_partner_node     (MUTACIÓN: crea/recupera partner)
  → create_odoo_quote_node  (MUTACIÓN: crea sale.order + líneas)
  → error_node              (terminal)
END
```

### Lógica interna del nodo

```python
# TOOL-CALLING: el LLM consulta Odoo libremente aquí.
# Solo lectura — si falla, el flujo continúa sin contexto enriquecido.
async def enrich_context_node(state, config):
    deps = _get_deps(config)
    tools = build_odoo_tools(deps.odoo_service)
    llm_with_tools = deps.llm.bind_tools(tools)

    response = await llm_with_tools.ainvoke(state["messages"])

    # Ejecuta las tool calls que el LLM solicitó
    tool_results = await _run_tool_calls(response, tools)

    return {
        "messages": state["messages"] + [response] + tool_results,
        "odoo_context": _extract_context(tool_results),
    }
```

---

## Contrato de datos

### `state["odoo_context"]` (nuevo campo en ambos agentes)

```python
{
    "cliente": {...} | None,        # resultado de find_client o historial_cliente
    "productos": [...],             # resultados de buscar_productos
    "ordenes_previas": [...],       # órdenes anteriores del cliente
    "tickets_previos": [...],       # tickets anteriores del cliente
}
```

Los nodos de mutación pueden leer este campo para tomar mejores decisiones (p.ej., si el cliente ya tiene 3 tickets abiertos, marcar el nuevo con prioridad alta).

---

## Tests

### `tests/test_odoo_tools.py`

- Mock de `OdooService` con `unittest.mock.MagicMock`
- Verificar que cada tool llama al método correcto del servicio
- Verificar que las tools devuelven los tipos correctos
- Verificar que errores del servicio se propagan correctamente

### Tests de integración (requieren Odoo corriendo)

- `test_enrich_context_node`: verifica que el nodo enriquece el state con datos reales de Odoo
- Extender `test_odoo_api_wrapper.py` con métodos nuevos de `OdooService`

---

## Orden de implementación

1. Fix `odoo/helpers.py` — typo `jelpdesk.ticket`
2. Crear `odoo/service.py` — OdooService con todos los métodos
3. Crear `odoo/tools.py` — build_odoo_tools()
4. Actualizar `agents/*/dependencies.py` — usar OdooService
5. Actualizar `agents/*/state.py` — añadir odoo_context
6. Añadir `enrich_context_node` a cada agente (nodes.py + graph.py)
7. Escribir tests en `test_odoo_tools.py`
8. Verificar pipeline completo end-to-end

---

## Fuera de alcance (próximas iteraciones)

- Exponer las tools via MCP (Opción C) — pendiente recordar al usuario
- HITL (Human-in-the-Loop) en nodos de mutación
- Disk-based memory persistente
- WebSocket frontend
- Semantic router para clasificación de intención
