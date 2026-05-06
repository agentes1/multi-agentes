# Multi-Agentes — Asistente Virtual para Odoo 18

Backend Python multi-agente que automatiza la clasificación de solicitudes de clientes, la creación de tickets de helpdesk y la generación de presupuestos comerciales directamente en Odoo 18.

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-orange)
![Odoo](https://img.shields.io/badge/Odoo-18.0-714B67?logo=odoo&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-261230)
![Type checked: Mypy](https://img.shields.io/badge/type%20checked-mypy-blue)

---

## Tabla de contenidos

- [Descripción](#descripcion)
- [Características](#caracteristicas)
- [Arquitectura](#arquitectura)
- [Stack tecnológico](#stack-tecnologico)
- [Requisitos previos](#requisitos-previos)
- [Instalación local](#instalacion-local)
- [Configuración](#configuracion)
- [Uso](#uso)
  - [Backend local](#backend-local)
  - [Docker Compose (stack completo)](#docker-compose-stack-completo)
  - [Bootstrap de Odoo](#bootstrap-de-odoo)
- [Flujo actual](#flujo-actual)
  - [Correo entrante](#correo-entrante)
  - [Ticket nuevo en Helpdesk](#ticket-nuevo-en-helpdesk)
  - [Mensajes posteriores en Discuss](#mensajes-posteriores-en-discuss)
  - [Presupuesto al pasar a Ready for next stage](#presupuesto-al-pasar-a-ready-for-next-stage)
- [API Reference](#api-reference)
- [Router semántico](#router-semantico)
- [Tests](#tests)
- [Calidad de código](#calidad-de-codigo)
- [Evaluación de modelos](#evaluacion-de-modelos)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Troubleshooting](#troubleshooting)
- [Comandos rápidos](#comandos-rapidos)
- [Contribuir](#contribuir)

---

## Descripcion

El sistema expone una API FastAPI que actúa como backend inteligente de Odoo. Los addons custom de Odoo llaman a endpoints específicos según el origen de la acción:

| Endpoint | Dispara cuando |
|---|---|
| `POST /assistant/incoming-email` | Odoo recibe un correo entrante |
| `POST /assistant/ticket-entry` | Se crea un ticket de helpdesk |
| `POST /assistant/discuss-message` | El cliente escribe en el chat de Discuss |
| `POST /assistant/budget-from-ticket` | El ticket pasa a **Ready for next stage** |
| `POST /assistant/sales-from-ticket` | El ticket se clasifica como oportunidad de venta |

---

## Caracteristicas

- **Procesamiento de correos entrantes**: convierte emails en tickets de helpdesk estructurados usando LLM.
- **Router semántico determinista**: clasifica solicitudes en `budget`, `sales` o `discard` sin depender de embeddings.
- **Generación automática de presupuestos**: el agente selecciona productos reales del catálogo de Odoo y crea `sale.order`.
- **Gestión de oportunidades CRM**: crea `crm.lead` a partir de solicitudes de ventas.
- **Contexto conversacional**: mantiene el contexto de cada hilo de Discuss entre mensajes.
- **Integración nativa con Odoo 18**: XML-RPC + addons custom + MCP local para herramientas de agente.
- **Modelos locales**: 100 % offline mediante Ollama, sin dependencias de APIs externas de LLM.
- **Evaluación multi-modelo**: benchmark automatizado con DeepEval para comparar modelos Ollama.
- **Visualizador de pipeline**: interfaz web incluida (`frontend.html`) para probar endpoints manualmente.

---

## Arquitectura

```text
Correo / Ticket / Discuss  (Odoo)
         |
    addons custom
         |
    FastAPI  api.py
         |
   orchestration/          <-- adapta payloads y decide qué agente ejecutar
         |
    routing/               <-- router semántico (budget / sales / discard)
      /    \    \
agents/   agents/  agents/
intake    budget   sales / general
  |         |
  +----+----+
       |
  odoo/api_wrapper.py      <-- cliente XML-RPC nativo
  odoo/odoo_mcp_server.py  <-- herramientas MCP (catálogo, clientes, presupuestos)
  odoo/mcp_client.py       <-- cliente MCP usado por los agentes
```

### Agentes

| Agente | Framework | Rol |
|---|---|---|
| `intake_agent` | LangGraph | Extrae datos del correo/ticket y crea `helpdesk.ticket` |
| `budget_agent` | LangGraph | Lee el ticket, selecciona productos y crea `sale.order` |
| `sales_agent` | LangGraph | Crea `crm.lead` para oportunidades comerciales |
| `general_agent` | LangChain | Respuesta de fallback para solicitudes no accionables |
| `assistant_chat_agent` | LangChain | Respuestas contextuales en hilos de Discuss |

### Flujo principal: email a presupuesto

```text
Email  -->  mail_inbox_input (addon)  -->  /assistant/incoming-email
  -->  IntakeAgent (extrae + crea ticket)
  -->  [usuario mueve ticket a "Ready for next stage"]
  -->  helpdesk_virtual_assistant (addon)  -->  /assistant/budget-from-ticket
  -->  BudgetAgent (selecciona productos + crea sale.order)
  -->  Respuesta en Discuss
```

---

## Stack tecnologico

| Capa | Tecnología |
|---|---|
| API | FastAPI + Uvicorn |
| Agentes | LangGraph 0.2, LangChain Core |
| LLM runtime | Ollama (modelos locales) |
| ERP | Odoo 18.0 (XML-RPC) |
| Herramientas MCP | FastMCP |
| Validación | Pydantic v2 |
| Evaluación | DeepEval 3.9.5 |
| Linter/formateador | Ruff |
| Tipos | Mypy |
| Tests | Pytest + pytest-asyncio |
| Contenedores | Docker + Docker Compose |
| Base de datos | PostgreSQL 15 (para Odoo) |

---

## Requisitos previos

- **Python 3.13.x** (no compatible con versiones anteriores ni con 3.14+)
- **Docker** y **Docker Compose** (para levantar el stack completo)
- **Ollama** en ejecución con al menos un modelo descargado:
# Multi-agentes

Backend Python multi-agente integrado con Odoo 18 para clasificar solicitudes de clientes, crear tickets de helpdesk y generar presupuestos comerciales en Odoo.

El flujo actual no usa un endpoint generico `/process`: Odoo llama a endpoints especificos del backend segun el origen de la accion:

1. `/assistant/incoming-email`: procesa correos entrantes guardados por Odoo.
2. `/assistant/ticket-entry`: procesa tickets de helpdesk ya creados.
3. `/assistant/discuss-message`: procesa mensajes posteriores en el chat de Discuss.
4. `/assistant/budget-from-ticket`: crea el presupuesto cuando un ticket pasa a Ready for next stage.

## 1. Arquitectura

```text
Correo / ticket / Discuss en Odoo
  -> addons custom de Odoo
  -> FastAPI (api.py)
  -> orquestadores (orchestration/)
  -> router semantico (routing/)
  -> agentes LangGraph (agents/)
  -> Odoo XML-RPC / tools MCP locales
```

Componentes principales:

- `api.py`: capa HTTP con FastAPI. Mantiene endpoints finos y delega la logica.
- `orchestration/`: adapta payloads externos y decide que agente ejecutar.
- `routing/`: router semantico determinista para clasificar texto como `budget` o `discard`.
- `agents/intake_agent/`: convierte correos entrantes en tickets de helpdesk.
- `agents/budget_agent/`: lee el contenido completo del ticket, selecciona productos reales del catalogo de Odoo y crea presupuestos.
- `agents/general_agent/`: respuesta fija para mensajes descartados o no accionables.
- `odoo/api_wrapper.py`: cliente XML-RPC para modelos de Odoo.
- `odoo/odoo_mcp_server.py` y `odoo/mcp_client.py`: tools locales tipo MCP para catalogo, clientes y presupuestos.
- `odoo/addons/`: addons Odoo incluidos o adaptados para helpdesk, correo entrante y asistente virtual.

## 2. Flujo actual

### 2.1 Correo entrante

1. Odoo recibe un correo mediante `fetchmail`/Gmail.
2. El addon `mail_inbox_input` crea un `mail.inbox.message`.
3. El registro queda en estado `new`. No se procesa dentro del `create()`.
4. El cron `Mail Inbox: Process intake queue` llama a `mail.inbox.message._cron_process_pending_intake()`.
5. `_cron_process_pending_intake()` marca el registro como `processing` y llama a `_trigger_intake_processing()`.
6. `_trigger_intake_processing()` construye el payload con `_build_backend_payload()` y llama a `POST /assistant/incoming-email`.
7. `IncomingEmailOrchestrator` adapta el correo a `source_input`.
8. `intake_agent` ejecuta este grafo:
   - `prepare_input_node`: normaliza email/chat a texto.
   - `extract_request_node`: pide al LLM un JSON estructurado.
   - `prepare_ticket_node`: mapea tipo, equipo, categoria, prioridad y etiquetas.
   - `create_ticket_node`: crea `helpdesk.ticket` en Odoo.
9. El ticket creado desde email se crea con contexto `assistant_ticket_origin=email`, `skip_virtual_assistant_chat=True` y `skip_virtual_assistant_followup=True`.
10. Por ese contexto, `helpdesk_virtual_assistant` no abre Discuss para ese ticket.
11. `IncomingEmailOrchestrator` reutiliza `TicketEntryOrchestrator` solo para generar el texto de respuesta al correo.
12. `mail_inbox_input` marca el email como `processed`, guarda `generated_ticket_id` y envia la respuesta por email.

### 2.2 Ticket nuevo en Helpdesk

1. Odoo crea un `helpdesk.ticket`.
2. `helpdesk_virtual_assistant` abre un chat `Ticket <id> - Asistente Virtual`.
3. El addon publica un primer mensaje fijo de recepcion.
4. El addon llama a `POST /assistant/ticket-entry`.
5. `TicketEntryOrchestrator` construye texto enrutable y ejecuta `routing.semantic_router.router`.
6. Si la ruta es `budget`, no crea presupuesto todavia. Responde que el presupuesto se creara cuando el ticket este en Ready for next stage.
7. Si la ruta es `discard` o `issue`, responde `general_agent`.

Importante: crear un ticket a mano no crea un presupuesto. El presupuesto se dispara despues, al pasar el ticket a Ready for next stage.

### 2.3 Mensajes posteriores en Discuss

1. El usuario escribe en el chat de Discuss abierto para el ticket.
2. La extension de `mail.message` detecta canales con formato `Ticket <id> - Asistente Virtual`.
3. Ignora mensajes escritos por el propio asistente para evitar bucles.
4. Llama a `POST /assistant/discuss-message`.
5. `DiscussMessageOrchestrator` enruta solo el mensaje nuevo, no el titulo historico del ticket.
6. Si el mensaje pide presupuesto, responde que se creara al pasar el ticket a Ready for next stage.
7. Si no es presupuesto, devuelve fallback general o no publica nada util.

### 2.4 Presupuesto al pasar a Ready for next stage

El presupuesto se crea desde Odoo cuando cambia el ticket:

1. El usuario mueve el ticket a Ready for next stage.
2. `helpdesk.ticket.write()` detecta `kanban_state == "done"`.
3. Si el ticket no tiene `assistant_budget_created` ni `assistant_sale_order_id`, llama a `_trigger_budget_from_ready_state()`.
4. `_trigger_budget_from_ready_state()` llama a `POST /assistant/budget-from-ticket`.
5. `BudgetFromTicketOrchestrator` ejecuta `budget_agent`.

El grafo de `budget_agent` ejecuta:

1. `prepare_budget_node`: recibe el contenido del ticket tal cual, extrae `company_name`, `project_summary` y `requirements` con el LLM, obtiene el catalogo real de Odoo con `list_catalog()` y pide al LLM que seleccione `product_ids` validos.
2. `create_odoo_quote_node`: crea o reutiliza un `sale.order`. Usa `client_order_ref = helpdesk-ticket-<ticket_id>` para evitar duplicados.
3. `compose_budget_reply_node`: redacta una respuesta final con LLM. Si el LLM falla, usa una respuesta fallback.

El resultado incluye `quote_summary` con `sale_order_id`, productos, lineas, subtotal, total y moneda.

Odoo guarda el resultado en el ticket:

- `assistant_budget_created`
- `assistant_sale_order_id`
- `assistant_budget_response`

## 3. Requisitos

- Python 3.13.x.
- Docker y Docker Compose, si se quiere levantar Odoo localmente.
- Ollama en ejecucion para los nodos que usan LLM.
- Un modelo local de Ollama, por ejemplo:

```bash
ollama pull qwen3:4b
```

## 4. Instalacion local

Desde la raiz del proyecto:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 5. Variables de entorno

El codigo carga variables con `python-dotenv` desde `.env`.

Ejemplo para ejecucion local:

```env
URL=http://localhost:8069
DB=odoo
USERNAME=odoo
PASSWORD=multi-agente-agentes1

ODOO_BASE_URL=http://localhost:8069/xmlrpc/2
ODOO_DB=odoo
ODOO_USERNAME=odoo
ODOO_PASSWORD=multi-agente-agentes1

OLLAMA_MODEL=qwen3:4b
OLLAMA_TEMPERATURE=0
```

Variables opcionales:

- `OLLAMA_MODEL_OVERRIDE`: cambia el modelo sin modificar `.env`.
- `OLLAMA_TEMPERATURE_OVERRIDE`: cambia temperatura en ejecuciones puntuales.
- `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`: se usan en `scripts/bootstrap_odoo.py` para configurar Gmail OAuth en Odoo.


## 6. Ejecutar

### 6.1 Backend local

```bash
python api.py
```

La API queda disponible en:

- Healthcheck: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`

Comprobar salud:

```bash
curl http://localhost:8000/health
```

Respuesta esperada:

```json
{"status":"ok"}
```

### 6.2 Odoo + backend con Docker

```bash
docker compose up --build
```

Servicios:

- Backend: `http://localhost:8000`
- Odoo: `http://localhost:8069`
- Postgres: servicio interno `db`

Dentro de Docker:

- Odoo llama al backend por `http://assistant-backend:8000`.
- El backend llama a Odoo por `http://web:8069/xmlrpc/2`.
- Los addons se montan desde `./odoo/addons` en `/mnt/extra-addons`.

Con Odoo levantado, ejecuta el script de inicialización **una sola vez**:

```powershell
$env:PYTHONPATH=(Get-Location).Path
python .\scripts\bootstrap_odoo.py
```

El bootstrap:

- Instala los módulos base y los addons custom (`helpdesk_virtual_assistant`, `mail_inbox_input`)
- Crea productos presupuestables de referencia con `default_code`
- Crea contactos y empresas demo
- Configura equipos, tipos, categorías, estados y etiquetas de helpdesk
- Crea el usuario interno **Asistente Virtual**
- Registra las URLs de callback del backend en los parámetros de sistema de Odoo
- Configura OAuth de Gmail si las variables `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` están definidas

---

## Flujo actual

### Correo entrante

1. Odoo recibe un correo mediante `fetchmail`/Gmail.
2. El addon `mail_inbox_input` crea un `mail.inbox.message`.
3. El registro queda en estado `new`. No se procesa dentro del `create()`.
4. El cron `Mail Inbox: Process intake queue` llama a `mail.inbox.message._cron_process_pending_intake()`.
5. `_cron_process_pending_intake()` marca el registro como `processing` y llama a `_trigger_intake_processing()`.
6. `_trigger_intake_processing()` construye el payload con `_build_backend_payload()` y llama a `POST /assistant/incoming-email`.
7. `IncomingEmailOrchestrator` adapta el correo a `source_input`.
8. `intake_agent` ejecuta este grafo:
   - `prepare_input_node`: normaliza email/chat a texto.
   - `extract_request_node`: pide al LLM un JSON estructurado.
   - `prepare_ticket_node`: mapea tipo, equipo, categoría, prioridad y etiquetas.
   - `create_ticket_node`: crea `helpdesk.ticket` en Odoo.
9. El ticket creado desde email se crea con contexto `assistant_ticket_origin=email`, `skip_virtual_assistant_chat=True` y `skip_virtual_assistant_followup=True`.
10. Por ese contexto, `helpdesk_virtual_assistant` no abre Discuss para ese ticket.
11. `IncomingEmailOrchestrator` reutiliza `TicketEntryOrchestrator` solo para generar el texto de respuesta al correo.
12. `mail_inbox_input` marca el email como `processed`, guarda `generated_ticket_id` y envía la respuesta por email.

---

### Ticket nuevo en Helpdesk

1. Odoo crea un `helpdesk.ticket`.
2. `helpdesk_virtual_assistant` abre un chat `Ticket <id> - Asistente Virtual`.
3. El addon publica un primer mensaje fijo de recepción.
4. El addon llama a `POST /assistant/ticket-entry`.
5. `TicketEntryOrchestrator` construye texto enrutable y ejecuta `routing.semantic_router.router`.
6. Si la ruta es `budget`, no crea presupuesto todavía. Responde que el presupuesto se creará cuando el ticket esté en **Ready for next stage**.
7. Si la ruta es `discard` o `issue`, responde con `general_agent`.

> **Importante:** crear un ticket manualmente no genera un presupuesto. El presupuesto se dispara al pasar el ticket a **Ready for next stage**.

---

### Mensajes posteriores en Discuss

1. El usuario escribe en el chat de Discuss abierto para el ticket.
2. La extensión de `mail.message` detecta canales con formato `Ticket <id> - Asistente Virtual`.
3. Ignora mensajes escritos por el propio asistente para evitar bucles.
4. Llama a `POST /assistant/discuss-message`.
5. `DiscussMessageOrchestrator` decide la ruta usando el mensaje nuevo junto con contexto reciente del hilo, incluyendo `assistant_route_name` y `recent_messages`.
6. Si detecta intención de presupuesto o de avanzar el flujo, puede responder con confirmaciones contextualizadas y preparar la siguiente acción esperada.
7. Además del texto de respuesta o un fallback general, puede devolver `actions` (por ejemplo, `mark_ticket_ready`) para que Odoo ejecute cambios sobre el ticket cuando corresponda.

---

### Presupuesto al pasar a Ready for next stage

El presupuesto se crea desde Odoo cuando cambia el estado del ticket:

1. El usuario mueve el ticket a **Ready for next stage**.
2. `helpdesk.ticket.write()` detecta `kanban_state == "done"`.
3. Si el ticket no tiene `assistant_budget_created` ni `assistant_sale_order_id`, llama a `_trigger_budget_from_ready_state()`.
4. `_trigger_budget_from_ready_state()` llama a `POST /assistant/budget-from-ticket`.
5. `BudgetFromTicketOrchestrator` ejecuta `budget_agent`.

El grafo de `budget_agent` ejecuta en orden:

1. **`prepare_budget_node`**: recibe el contenido del ticket tal cual, extrae `company_name`, `project_summary` y `requirements` con el LLM, obtiene el catálogo real de Odoo con `list_catalog()` y pide al LLM que seleccione `product_ids` válidos.
2. **`create_odoo_quote_node`**: crea o reutiliza un `sale.order`. Usa `client_order_ref = helpdesk-ticket-<ticket_id>` para evitar duplicados.
3. **`compose_budget_reply_node`**: redacta una respuesta final con LLM. Si el LLM falla, usa una respuesta fallback.

El resultado incluye `quote_summary` con `sale_order_id`, productos, líneas, subtotal, total y moneda.

Odoo guarda el resultado en el ticket en los campos:

- `assistant_budget_created`
- `assistant_sale_order_id`
- `assistant_budget_response`
- instala modulos base y addons custom;
- instala `mail_inbox_input` y `helpdesk_virtual_assistant`;
- crea productos presupuestables de referencia;
- crea contactos demo;
- crea equipos, tipos, categorias, estados y etiquetas de helpdesk;
- crea el usuario interno `Asistente Virtual`;
- configura URLs internas para ticket entry, Discuss, incoming email y budget from ticket;
- configura parametros de Gmail OAuth si existen en el entorno.

## 7. Endpoints

### 7.1 `GET /health`

Devuelve:

```json
{"status":"ok"}
```

### 7.2 `POST /assistant/incoming-email`

### `GET /health`

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok"}
```

---

### `POST /assistant/incoming-email`

Llamado por el addon `mail_inbox_input` antes de crear el ticket definitivo.
Entrada usada por `mail_inbox_input` antes de crear el ticket definitivo.

```bash
curl -X POST http://localhost:8000/assistant/incoming-email \
  -H "Content-Type: application/json" \
  -d '{
    "inbox_id": 1,
    "subject": "Solicitud de presupuesto",
    "email_from": "Ana <ana@acme.com>",
    "body": "Necesitamos implantar CRM y automatizacion comercial.",
    "thread_id": "manual-email-1"
  }'
```

Respuesta resumida:

```json
{
  "ok": true,
  "ticket_id": 321,
  "final_text": "He detectado que este ticket puede requerir presupuesto. Cuando lo marques como Ready for next stage creare el presupuesto.",
  "reply_text": "He detectado que este ticket puede requerir presupuesto. Cuando lo marques como Ready for next stage creare el presupuesto.",
  "route_name": "budget",
  "agent_name": null,
  "normalized_request": {
    "company_name": "ACME",
    "project_summary": "Solicitud de presupuesto CRM",
    "requirements": ["CRM", "automatizacion comercial"],
    "urgency": "media",
    "ticket_type": "budget",
    "missing_information": []
  },
  "ticket_payload": {
    "team_name": "Presupuestos",
    "type_name": "Presupuesto",
    "category_name": "Consulta presupuesto"
  },
  "warnings": [],
  "error": null,
  "trace": ["incoming_email_received", "ticket_type_decided:budget", "ticket_created:321", "ticket_received", "route_decided:budget", "budget_waiting_ready_state"]
}
```

### 7.3 `POST /assistant/ticket-entry`

Entrada usada cuando ya existe un `helpdesk.ticket`.

```bash
curl -X POST http://localhost:8000/assistant/ticket-entry \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": 100,
    "title": "Solicitud presupuesto CRM",
    "description": "Necesitamos CRM y automatizacion comercial en Odoo.",
    "partner_name": "ACME",
    "partner_email": "ana@acme.com",
    "thread_id": "manual-ticket-100"
  }'
```

Respuesta:

```json
{
  "ok": true,
  "route_name": "budget",
  "agent_name": null,
  "reply_text": "He detectado que este ticket puede requerir presupuesto. Cuando lo marques como Ready for next stage creare el presupuesto.",
  "normalized_request": {},
  "quote_summary": {},
  "error": null,
  "trace": ["ticket_received", "route_decided:budget", "budget_waiting_ready_state"]
}
```

---
Respuesta resumida:

```json
{
  "ok": true,
  "route_name": "budget",
  "agent_name": null,
  "reply_text": "He detectado que este ticket puede requerir presupuesto. Cuando lo marques como Ready for next stage creare el presupuesto.",
  "normalized_request": {},
  "quote_summary": {},
  "error": null,
  "trace": ["ticket_received", "route_decided:budget", "budget_waiting_ready_state"]
}
```

### 7.4 `POST /assistant/discuss-message`

Entrada usada para mensajes posteriores en Discuss.

```bash
curl -X POST http://localhost:8000/assistant/discuss-message \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": 100,
    "ticket_title": "Solicitud inicial",
    "channel_id": 7,
    "channel_name": "Ticket 100 - Asistente Virtual",
    "message_id": 12,
    "author_name": "Ana",
    "author_email": "ana@acme.com",
    "body": "Necesito presupuesto para CRM.",
    "thread_id": "manual-discuss-7"
  }'
```

Respuesta resumida para un mensaje de presupuesto:

```json
{
  "ok": true,
  "route_name": "budget",
  "agent_name": null,
  "reply_text": "He detectado que este mensaje puede requerir presupuesto. Creare el presupuesto cuando el ticket este marcado como Ready for next stage.",
  "normalized_request": {},
  "quote_summary": {},
  "error": null,
  "trace": ["discuss_message_received", "route_decided:budget", "budget_waiting_ready_state"]
}
```

---

### 7.5 `POST /assistant/budget-from-ticket`

Entrada usada por `helpdesk_virtual_assistant` cuando un ticket pasa a Ready for next stage.

```bash
curl -X POST http://localhost:8000/assistant/budget-from-ticket \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": 100,
    "title": "Solicitud presupuesto CRM",
    "description": "Necesitamos CRM y automatizacion comercial en Odoo.",
    "partner_id": 12,
    "partner_name": "ACME",
    "partner_email": "ana@acme.com",
    "thread_id": "manual-budget-100"
  }'
```

Respuesta resumida:

```json
{
  "ok": true,
  "agent_name": "budget_agent",
  "reply_text": "He generado un presupuesto inicial en Odoo...",
  "sale_order_id": 55,
  "normalized_request": {
    "company_name": "ACME",
    "project_summary": "Solicitud presupuesto CRM",
    "requirements": ["CRM", "automatizacion comercial"]
  },
  "quote_summary": {
    "sale_order_id": 55,
    "client_order_ref": "helpdesk-ticket-100",
    "selected_products": [
      {"id": 3, "name": "CRM", "default_code": "crm"}
    ],
    "total": 1200.0,
    "currency": "EUR"
  },
  "error": null,
  "trace": ["budget_ticket_received", "agent_completed:budget_agent"]
}
```

## 8. Router semantico

El router vive en `routing/semantic_router.py` y usa:

- normalizacion de texto y acentos;
- tokens sin stopwords;
- coincidencias por keywords;
- similitud con utterances mediante `difflib.SequenceMatcher`;
- prioridad para señales comerciales claras de presupuesto.

Rutas actuales:

- `budget`: presupuesto, precio, propuesta, implantacion Odoo, CRM, ERP, ventas, formacion, soporte mensual, desarrollo a medida.
- `discard`: saludo, prueba, consulta general o mensaje sin accion clara.

El router vive en `routing/semantic_router.py` y usa un enfoque híbrido en capas:

- Normalización de texto y acentos.
- Tokenización sin stopwords.
- Coincidencias por keywords con listas de términos por ruta.
- Similitud con utterances de ejemplo mediante `difflib.SequenceMatcher` (peso 55 %).
- Prioridad para señales comerciales claras que fuerzan la ruta `budget` sin scoring adicional.
- Embeddings opcionales via Ollama para similitud coseno (activables con `ROUTER_EMBEDDINGS_ENABLED=true`, peso 25 %).

Rutas actuales:

| Ruta | Señales que la activan |
|---|---|
| `budget` | presupuesto, precio, propuesta, implantación Odoo, CRM, ERP, formación, soporte mensual, desarrollo a medida |
| `sales` | ventas, pipeline, leads, oportunidades, seguimiento comercial |
| `discard` | saludos, pruebas, consultas generales o mensajes sin acción clara |

---

## Tests

### Tests unitarios (sin Odoo real)
## 9. Tests

### 9.1 Tests rapidos sin Odoo real

Estos tests usan fakes/mocks y sirven para validar router, orquestadores HTTP y utilidades de evaluacion:

Usan fakes/mocks y sirven para validar router, orquestadores HTTP y utilidades de evaluación:

```bash
python -m pytest -q \
  tests/test_router.py \
  tests/test_assistant_entry.py \
  tests/test_assistant_email.py \
  tests/test_assistant_discuss.py \
  tests/test_intake_partner_assignment.py \
  tests/test_deepeval_eval.py
```

En PowerShell:

```powershell
python -m pytest -q tests/test_router.py tests/test_assistant_entry.py tests/test_assistant_email.py tests/test_assistant_discuss.py tests/test_intake_partner_assignment.py tests/test_deepeval_eval.py
```

### 9.2 Tests de integracion con Odoo

Los tests marcados con `@pytest.mark.integration` necesitan Odoo levantado, datos bootstrap y variables de entorno correctas.

Los tests marcados con `@pytest.mark.integration` necesitan Odoo levantado, datos de bootstrap y variables de entorno correctas.

```bash
python -m pytest -q -m integration
```

Para excluirlos:

```bash
python -m pytest -q -m "not integration"
```

### 9.3 Tests por area

```bash
# Router semantico
python -m pytest -q tests/test_router.py

# Orquestadores de API actuales y asignacion de empresas
python -m pytest -q tests/test_assistant_entry.py tests/test_assistant_email.py tests/test_assistant_discuss.py tests/test_intake_partner_assignment.py

# Agente intake contra Odoo real
python -m pytest -q tests/test_intake_agent.py

# Agente de presupuestos contra Odoo real
python -m pytest -q tests/test_budget_agent.py

# Evaluacion DeepEval estructural
python -m pytest -q tests/test_deepeval_eval.py
```

> **Aviso:** `tests/test_api.py` hay que modificarlo o eliminarlo antes de ejecutar la suite completa.

---

## 10. Calidad y formato

El proyecto configura Ruff, Mypy y Pytest en `pyproject.toml`.

Comandos utiles:

```bash
# Formato
python -m ruff format .

# Lint con autofix
python -m ruff check . --fix

# Type checking
python -m mypy .
```

Pre-commit:

```bash
python -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## 11. Evaluaciones y benchmark de modelos

DeepEval se usa en `shared/deepeval_eval.py` con:

- `AnswerRelevancyMetric` — relevancia de la respuesta generada.
- `GEval` con criterio de calidad de presupuesto — calidad del JSON de presupuesto extraído.
- Modelo evaluador local mediante Ollama (sin dependencias de nube).

### Ejecutar tests estructurales de DeepEval

```bash
python -m pytest -q tests/test_deepeval_eval.py
```

Ejecutar benchmark multi-modelo:

```bash
python -m evals.run_multi_model_eval \
  --cases evals/benchmark_cases.jsonl \
  --models qwen3:4b llama3.2 mistral \
  --out-dir evals/reports
```

Tambien puedes editar `evals/models.yaml` y ejecutar:

```bash
python -m evals.run_multi_model_eval
```

Salida generada en `evals/reports/`:

- `*.json` — resultados detallados por modelo y caso.
- `*.md` — tabla comparativa markdown con ganador global según las reglas de `evals/reporting.py`.

- JSON detallado en `evals/reports/`.
- Markdown comparativo en `evals/reports/`.
- ganador global segun las reglas de `evals/reporting.py`.

Guia ampliada: `docs/model_evaluation_guide.md`.

## 12. Estructura del repositorio

```text
.
├── api.py
├── agents/
│   ├── budget_agent/
│   ├── general_agent/
│   └── intake_agent/
├── orchestration/
├── routing/
├── shared/
├── odoo/
│   ├── addons/
│   ├── api_wrapper.py
│   ├── mcp_client.py
│   └── odoo_mcp_server.py
├── scripts/
│   └── bootstrap_odoo.py
├── tests/
├── evals/
└── docs/
```

## 13. Troubleshooting

### `ModuleNotFoundError`

Activa el entorno virtual e instala las dependencias:

```bash
python -m pip install -r requirements.txt
```

### El backend no conecta con Odoo

Comprueba:

- que Odoo este levantado en `http://localhost:8069` o en `http://web:8069` dentro de Docker;
- que `ODOO_BASE_URL`, `ODOO_DB`, `ODOO_USERNAME` y `ODOO_PASSWORD` sean correctos;
- que la base de datos exista;
- que los addons esten instalados y actualizados.

### El LLM no responde

Comprueba:

```bash
ollama list
ollama run qwen3:4b
```

Y revisa `OLLAMA_MODEL`.

### Docker Compose falla por variables

El compose usa variables de entorno para interpolar credenciales y tambien referencia `./shared/.env`. Crea ese archivo, exporta variables en la shell o ajusta `docker-compose.yml`.

### El router devuelve `discard`

El router solo clasifica como `budget` si el texto contiene señales comerciales claras: al menos un término comercial (`presupuesto`, `precio`, `propuesta`) combinado con un término de alcance (`CRM`, `ERP`, `Odoo`, `implantación`, `ventas`, `automatización`).

### El presupuesto no encuentra productos

`budget_agent` obtiene el catálogo real con `list_catalog()` y el LLM elige ids de producto de esa lista. Ejecuta el bootstrap o crea productos activos con `default_code`:

```text
crm | automatizacion_comercial | helpdesk | sales
implantacion_odoo | formacion | soporte_mensual | desarrollo_medida
```

### El presupuesto no se genera al crear un ticket manualmente

Es el comportamiento esperado. El ticket manual solo abre el chat de asistente y llama a `/assistant/ticket-entry`. El presupuesto se crea únicamente cuando el ticket pasa a **Ready for next stage**.

### El presupuesto no se crea al mover el ticket a Ready for next stage

`budget_agent` obtiene el catalogo real con `list_catalog()` y el LLM elige ids de producto de esa lista. Ejecuta el bootstrap o crea productos activos con `default_code`, por ejemplo:

- Aparece una llamada a `POST /assistant/budget-from-ticket` en los logs del backend.
- El cambio de etapa escribe realmente `kanban_state = "done"`.
- El ticket no tiene ya `assistant_budget_created` o `assistant_sale_order_id`.
- El catálogo tiene productos activos con `default_code`.
- El backend puede contactar con Odoo y con Ollama.

---

## Comandos rapidos

```bash
# Instalar dependencias
python -m pip install -r requirements.txt

# Ejecutar backend
python api.py

# Levantar Odoo + backend + Postgres + Ollama
docker compose up --build

# Bootstrap de Odoo (una sola vez)
python scripts/bootstrap_odoo.py

# Tests rápidos (sin Odoo)
python -m pytest -q tests/test_router.py tests/test_assistant_entry.py \
  tests/test_assistant_email.py tests/test_assistant_discuss.py \
  tests/test_intake_partner_assignment.py tests/test_deepeval_eval.py

# Tests de integración (con Odoo levantado)
python -m pytest -q -m integration

# Benchmark multi-modelo
python -m evals.run_multi_model_eval

# Lint + formato
python -m ruff check . --fix && python -m ruff format .

# Type checking
python -m mypy .
```

---
- `crm`
- `automatizacion_comercial`
- `helpdesk`
- `sales`
- `implantacion_odoo`
- `formacion`
- `soporte_mensual`
- `desarrollo_medida`

### El presupuesto no se crea al crear un ticket manual

Es el comportamiento esperado. El ticket manual solo abre el chat de asistente y llama a `/assistant/ticket-entry`.

El presupuesto se crea cuando el ticket pasa a Ready for next stage, que actualmente se detecta con:

```python
kanban_state == "done"
```

Si al moverlo a Ready no se crea presupuesto, revisa:

- que aparezca una llamada a `POST /assistant/budget-from-ticket` en los logs;
- que el cambio de etapa escriba realmente `kanban_state = "done"`;
- que el ticket no tenga ya `assistant_budget_created` o `assistant_sale_order_id`;
- que el catalogo tenga productos activos con `default_code`;
- que el backend pueda contactar con Odoo y Ollama.

## 14. Comandos rapidos

```bash
# Instalar dependencias
python -m pip install -r requirements.txt

# Ejecutar backend
python api.py

# Levantar Odoo + backend + Postgres
docker compose up --build

# Bootstrap de Odoo
python scripts/bootstrap_odoo.py

# Tests rapidos
python -m pytest -q tests/test_router.py tests/test_assistant_entry.py tests/test_assistant_email.py tests/test_assistant_discuss.py tests/test_intake_partner_assignment.py tests/test_deepeval_eval.py

# Tests de integracion
python -m pytest -q -m integration

# Benchmark modelos
python -m evals.run_multi_model_eval
```
