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

```bash
ollama pull qwen3:4b
```

---

## Instalacion local

```powershell
# 1. Clonar el repositorio
git clone <url-repositorio>
cd Proy_4

# 2. Crear y activar el entorno virtual
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Instalar dependencias
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## Configuracion

El proyecto carga variables de entorno con `python-dotenv` desde `.env` en la raíz del proyecto.

Crea un archivo `.env` basándote en el siguiente ejemplo:

```env
# ── Odoo (XML-RPC) ──────────────────────────────────────────────────
ODOO_BASE_URL=http://localhost:8069/xmlrpc/2
ODOO_DB=odoo
ODOO_USERNAME=odoo
ODOO_PASSWORD=<tu-password>

# ── Odoo (MCP Server) ───────────────────────────────────────────────
URL=http://localhost:8069
DB=odoo
USERNAME=odoo
PASSWORD=<tu-password>

# ── Ollama ──────────────────────────────────────────────────────────
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_TEMPERATURE=0

# ── Modelos por agente (opcional, sobreescriben OLLAMA_MODEL) ───────
MODEL_INTAKE_AGENT=llama3.2
MODEL_BUDGET_AGENT=qwen3:4b
MODEL_GENERAL_AGENT=qwen3:4b
MODEL_SALES_AGENT=qwen3:4b
MODEL_EVAL_JUDGE=qwen3:4b

# ── Router semántico (opcional) ──────────────────────────────────────
ROUTER_EMBEDDINGS_ENABLED=false
ROUTER_EMBED_MODEL=qwen3:4b

# ── Google OAuth para Gmail (opcional) ──────────────────────────────
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

### Variables de override en tiempo de ejecución

| Variable | Efecto |
|---|---|
| `OLLAMA_MODEL_OVERRIDE` | Cambia el modelo sin modificar `.env` |
| `OLLAMA_TEMPERATURE_OVERRIDE` | Cambia la temperatura para una ejecución puntual |

### Variables en Docker Compose

Dentro del stack Docker, las URLs internas cambian automáticamente:

- Backend llama a Odoo en `http://web:8069/xmlrpc/2`
- Odoo llama al backend en `http://assistant-backend:8000`

---

## Uso

### Backend local

```bash
python api.py
```

| Recurso | URL |
|---|---|
| API base | `http://localhost:8000` |
| Swagger UI | `http://localhost:8000/docs` |
| Healthcheck | `http://localhost:8000/health` |
| Visualizador de pipeline | Abrir `frontend.html` en el navegador |

Verificar que el backend está activo:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

### Docker Compose (stack completo)

Levanta Odoo 18, PostgreSQL, Ollama y el backend con un solo comando:

```bash
docker compose up --build
```

| Servicio | URL |
|---|---|
| Backend (FastAPI) | `http://localhost:8000` |
| Odoo | `http://localhost:8069` |
| Ollama | `http://localhost:11434` |
| PostgreSQL | Puerto interno `5432` |

Dentro de Docker:

- Odoo llama al backend por `http://assistant-backend:8000`.
- El backend llama a Odoo por `http://web:8069/xmlrpc/2`.
- Los addons se montan desde `./odoo/addons` en `/mnt/extra-addons`.

---

### Bootstrap de Odoo

Con Odoo levantado, ejecuta el script de inicialización **una sola vez**:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python .\scripts\bootstrap_odoo.py
```

El bootstrap realiza automáticamente:

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
5. `DiscussMessageOrchestrator` enruta solo el mensaje nuevo, no el título histórico del ticket.
6. Si el mensaje pide presupuesto, responde que se creará al pasar el ticket a **Ready for next stage**.
7. Si no es presupuesto, devuelve fallback general o no publica nada útil.

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

---

## API Reference

Todos los endpoints devuelven un envelope homogéneo:

```json
{
  "ok": true,
  "route_name": "budget",
  "agent_name": "budget_agent",
  "reply_text": "...",
  "error": null,
  "trace": ["step_1", "step_2"]
}
```

---

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

Respuesta:

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

---

### `POST /assistant/ticket-entry`

Llamado cuando ya existe un `helpdesk.ticket`.

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

### `POST /assistant/discuss-message`

Llamado por cada mensaje nuevo en el chat de Discuss.

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

Respuesta para un mensaje de presupuesto:

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

### `POST /assistant/budget-from-ticket`

Llamado por `helpdesk_virtual_assistant` cuando el ticket pasa a **Ready for next stage** (`kanban_state == "done"`).

```bash
curl -X POST http://localhost:8000/assistant/budget-from-ticket \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": 100,
    "title": "Solicitud presupuesto CRM",
    "description": "Necesitamos CRM y automatizacion comercial.",
    "partner_id": 12,
    "partner_name": "ACME",
    "partner_email": "ana@acme.com",
    "thread_id": "manual-budget-100"
  }'
```

Respuesta:

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

---

### `POST /assistant/sales-from-ticket`

Llamado cuando el ticket se clasifica como oportunidad de venta. Crea un `crm.lead` en Odoo.

---

## Router semantico

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

### Tests de integración (requieren Odoo levantado)

Los tests marcados con `@pytest.mark.integration` necesitan Odoo levantado, datos de bootstrap y variables de entorno correctas.

```bash
# Ejecutar solo integración
python -m pytest -q -m integration

# Excluir integración
python -m pytest -q -m "not integration"
```

### Tests por módulo

```bash
# Router semántico
python -m pytest -q tests/test_router.py

# Orquestadores y asignación de empresas
python -m pytest -q tests/test_assistant_entry.py tests/test_assistant_email.py \
  tests/test_assistant_discuss.py tests/test_intake_partner_assignment.py

# Agente intake contra Odoo real
python -m pytest -q tests/test_intake_agent.py

# Agente de presupuestos contra Odoo real
python -m pytest -q tests/test_budget_agent.py

# Evaluación DeepEval estructural
python -m pytest -q tests/test_deepeval_eval.py
```

> **Aviso:** `tests/test_api.py` hay que modificarlo o eliminarlo antes de ejecutar la suite completa.

---

## Calidad de codigo

El proyecto configura Ruff, Mypy y Pytest en `pyproject.toml`.

```bash
# Formatear código
python -m ruff format .

# Lint con autofix
python -m ruff check . --fix

# Type checking
python -m mypy .
```

### Pre-commit hooks

```bash
python -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

---

## Evaluacion de modelos

DeepEval está integrado en `shared/deepeval_eval.py` con las métricas:

- `AnswerRelevancyMetric` — relevancia de la respuesta generada.
- `GEval` con criterio de calidad de presupuesto — calidad del JSON de presupuesto extraído.
- Modelo evaluador local mediante Ollama (sin dependencias de nube).

### Ejecutar tests estructurales de DeepEval

```bash
python -m pytest -q tests/test_deepeval_eval.py
```

### Benchmark multi-modelo

```bash
# Especificando modelos en la línea de comandos
python -m evals.run_multi_model_eval \
  --cases evals/benchmark_cases.jsonl \
  --models qwen3:4b llama3.2 mistral \
  --out-dir evals/reports

# O editando evals/models.yaml y ejecutando sin argumentos
python -m evals.run_multi_model_eval
```

Salida generada en `evals/reports/`:

- `*.json` — resultados detallados por modelo y caso.
- `*.md` — tabla comparativa markdown con ganador global según las reglas de `evals/reporting.py`.

Guía ampliada: `docs/model_evaluation_guide.md`

---

## Estructura del repositorio

```text
.
├── api.py                        # Capa HTTP: FastAPI + endpoints
├── pyproject.toml                # Ruff, Mypy, Pytest
├── requirements.txt              # Dependencias fijadas (pip-compile)
├── requirements.in               # Dependencias de primer nivel
├── docker-compose.yml            # Odoo + Postgres + Ollama + Backend
├── Dockerfile                    # Imagen Python 3.13-slim del backend
├── frontend.html                 # Visualizador de pipeline (browser)
│
├── agents/
│   ├── intake_agent/             # Procesa correos y crea helpdesk.ticket
│   ├── budget_agent/             # Selecciona productos y crea sale.order
│   ├── sales_agent/              # Crea crm.lead para oportunidades
│   ├── general_agent/            # Respuesta fallback para solicitudes no accionables
│   └── assistant_chat_agent/     # Respuestas contextuales en Discuss
│
├── orchestration/                # Adapta payloads y orquesta agentes por endpoint
├── routing/                      # Router semántico (semantic_router.py, routes.py)
├── shared/                       # LLM factory, catálogo, DeepEval, notificaciones
│
├── odoo/
│   ├── api_wrapper.py            # Cliente XML-RPC nativo
│   ├── odoo_mcp_server.py        # Servidor MCP con herramientas de Odoo
│   ├── mcp_client.py             # Cliente MCP usado por los agentes
│   └── addons/                   # Addons Odoo custom
│       ├── helpdesk_virtual_assistant/
│       ├── mail_inbox_input/
│       ├── helpdesk_mgmt/
│       ├── helpdesk_type/
│       └── ...
│
├── scripts/
│   └── bootstrap_odoo.py         # Inicialización y seed de datos en Odoo
│
├── tests/                        # Suite de tests (pytest)
├── evals/                        # Benchmark multi-modelo + casos JSONL
└── docs/                         # Guías técnicas y contexto del proyecto
```

---

## Troubleshooting

### `ModuleNotFoundError` al ejecutar el backend

Activa el entorno virtual e instala las dependencias:

```bash
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### El backend no conecta con Odoo

Comprueba:

- Odoo está levantado en `http://localhost:8069` (local) o `http://web:8069` (Docker).
- `ODOO_BASE_URL`, `ODOO_DB`, `ODOO_USERNAME` y `ODOO_PASSWORD` son correctos.
- La base de datos existe y los addons están instalados y actualizados.

### Ollama no responde

```bash
ollama list          # muestra los modelos descargados
ollama run qwen3:4b  # prueba el modelo manualmente
```

Revisa también `OLLAMA_MODEL` y `OLLAMA_BASE_URL`.

### Docker Compose falla por variables de entorno

El compose usa variables de entorno para interpolar credenciales y también referencia `./shared/.env`. Crea ese archivo, exporta las variables en la shell o ajusta `docker-compose.yml`.

### El router devuelve siempre `discard`

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

Verifica:

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

## Contribuir

1. Crea una rama a partir de `main`:

   ```bash
   git checkout -b feat/mi-feature
   ```

2. Instala los pre-commit hooks:

   ```bash
   pre-commit install
   ```

3. Asegúrate de que los tests pasan antes de abrir un PR:

   ```bash
   python -m pytest -q -m "not integration"
   ```

4. Sigue el formato de commits convencional:

   ```
   feat: descripción del cambio
   fix: descripción del bug corregido
   refactor: descripción de la refactorización
   docs: actualización de documentación
   test: nuevos tests o correcciones
   chore: tareas de mantenimiento
   ```

5. Abre un Pull Request describiendo el problema que resuelve y cómo probarlo.
