# Multi-agentes

Backend Python multi-agente integrado con Odoo 18. El sistema clasifica solicitudes
de clientes, crea tickets de Helpdesk desde correos entrantes, conversa por Discuss
y, tras confirmacion, crea presupuestos de venta u oportunidades CRM en Odoo.

La API no usa un endpoint generico de procesamiento. Odoo llama a endpoints
especificos segun el origen de la accion:

1. `POST /assistant/incoming-email`: procesa correos entrantes guardados por Odoo.
2. `POST /assistant/ticket-entry`: responde al crear un ticket manual.
3. `POST /assistant/discuss-message`: responde a mensajes posteriores en Discuss.
4. `POST /assistant/budget-from-ticket`: crea presupuesto desde un ticket validado.
5. `POST /assistant/sales-from-ticket`: crea oportunidad CRM desde un ticket validado.

## Arquitectura

```text
Correo / ticket / Discuss en Odoo
  -> addons custom de Odoo
  -> FastAPI (api.py)
  -> orquestadores (orchestration/)
  -> router semantico (routing/)
  -> agentes LangGraph (agents/)
  -> tools locales Odoo MCP
  -> Odoo XML-RPC
```

Componentes principales:

- `api.py`: aplicacion FastAPI, modelos de entrada/salida y endpoints HTTP.
- `orchestration/`: adapta payloads de Odoo y decide que agente ejecutar.
- `routing/`: router hibrido con reglas, keywords, ejemplos y embeddings opcionales.
- `agents/intake_agent/`: convierte correos entrantes en tickets de Helpdesk.
- `agents/budget_agent/`: selecciona productos reales de Odoo y crea presupuestos.
- `agents/sales_agent/`: crea oportunidades comerciales en CRM.
- `agents/assistant_chat_agent/`: genera respuestas conversacionales de seguimiento.
- `agents/general_agent/`: respuesta de fallback cuando no hay intencion accionable.
- `odoo/api.py`: cliente XML-RPC generico para modelos de Odoo.
- `odoo/odoo_mcp_server.py`: tools locales para productos, clientes, tickets,
  presupuestos, oportunidades y mensajes.
- `odoo/addons/`: addons Odoo incluidos o adaptados para Helpdesk, correo entrante,
  asistente virtual, notificaciones y flujos comerciales.
- `scripts/bootstrap_odoo.py`: instalacion de modulos y datos demo.
- `evals/`: benchmark multi-modelo y reportes comparativos con DeepEval.

## Flujo Funcional

### 1. Correo Entrante

1. Odoo recibe un correo mediante `fetchmail`.
2. El addon `mail_inbox_input` crea un registro `mail.inbox.message` en estado `new`.
3. El cron procesa correos pendientes y llama al backend en
   `/assistant/incoming-email`.
4. `IncomingEmailOrchestrator` adapta el correo a `source_input`.
5. `intake_agent` ejecuta su grafo:
   - `prepare_input_node`: normaliza asunto, remitente y cuerpo.
   - `extract_request_node`: extrae JSON estructurado con el LLM.
   - `prepare_ticket_node`: asigna equipo, tipo, categoria, prioridad y etiquetas.
   - `create_ticket_node`: crea `helpdesk.ticket` en Odoo.
6. Si el correo ya fue procesado antes, el addon reutiliza el ticket generado.
7. El correo queda como `processed` o `error`.

Los tickets creados desde email se crean con contexto interno para evitar abrir
automaticamente el chat inicial del asistente.

### 2. Ticket Manual En Helpdesk

1. Al crear un `helpdesk.ticket`, el addon `helpdesk_virtual_assistant` abre un
   chat Discuss llamado `Ticket <id> - Asistente Virtual`.
2. Publica un mensaje fijo de recepcion.
3. Llama a `/assistant/ticket-entry`.
4. `TicketEntryOrchestrator` construye el texto enrutable y usa el router.
5. Segun la ruta:
   - `budget`: responde que ayudara a concretar el presupuesto antes de generarlo.
   - `sales`: responde que ayudara a concretar la oportunidad comercial.
   - `discard`: pide mas contexto o deriva a soporte/presupuesto/ventas.

Crear un ticket manual no crea todavia un presupuesto ni una oportunidad. La
creacion real ocurre cuando el ticket se marca como `Ready for next stage`.

### 3. Conversacion En Discuss

1. El usuario responde en el chat del ticket.
2. La extension de `mail.message` detecta el canal del asistente.
3. Ignora mensajes escritos por el propio asistente para evitar bucles.
4. Llama a `/assistant/discuss-message` con el mensaje actual, contexto del ticket
   e historial reciente.
5. `DiscussMessageOrchestrator` conserva la ruta guardada si el mensaje es corto
   o ambiguo.
6. Si el usuario confirma con una respuesta afirmativa y hay contexto de
   presupuesto o ventas, devuelve una accion `mark_ticket_ready`.
7. El addon aplica esa accion escribiendo `kanban_state = "done"` en el ticket.

Ese cambio de estado dispara el flujo de negocio correspondiente.

### 4. Presupuesto Al Pasar A Ready

Cuando un ticket queda listo y la ruta resuelta es `budget`:

1. Odoo llama a `/assistant/budget-from-ticket`.
2. `BudgetFromTicketOrchestrator` ejecuta `budget_agent`.
3. `budget_agent`:
   - analiza el contenido completo del ticket;
   - extrae empresa, resumen y requisitos;
   - busca o crea el contacto en Odoo si hace falta;
   - carga el catalogo real de productos;
   - selecciona productos por heuristicas o LLM;
   - crea o reutiliza un `sale.order`;
   - evita duplicados con una referencia basada en el ticket;
   - publica una respuesta en el chatter del ticket.
4. Odoo guarda el identificador del presupuesto y el texto generado.

### 5. Oportunidad CRM Al Pasar A Ready

Cuando la ruta resuelta es `sales`:

1. Odoo llama a `/assistant/sales-from-ticket`.
2. `SalesFromTicketOrchestrator` ejecuta `sales_agent`.
3. `sales_agent`:
   - extrae objetivos comerciales del ticket con el LLM;
   - resuelve o crea el contacto cliente;
   - consulta perfil e historial reciente;
   - comprueba si ya existe una oportunidad para ese ticket;
   - crea una oportunidad `crm.lead` de tipo `opportunity`;
   - redacta la respuesta final.
4. Odoo guarda el identificador de la oportunidad y el texto generado.

## Router Semantico

El router vive en `routing/semantic_router.py` y devuelve una de estas rutas:

- `budget`: presupuesto, precio, propuesta economica, implantacion, Odoo, CRM,
  ERP, formacion, soporte mensual, desarrollo o automatizacion con intencion
  economica clara.
- `sales`: ventas, pipeline, leads, oportunidades, seguimiento comercial o
  creacion de una oportunidad.
- `discard`: saludos, pruebas, soporte/incidencias sin intencion comercial o
  mensajes sin accion clara.

La clasificacion combina reglas prioritarias, tokens sin stopwords, keywords,
similitud con ejemplos mediante `difflib.SequenceMatcher` y embeddings de Ollama
si se activan en la configuracion.

## Requisitos

- Python 3.13.x.
- Docker y Docker Compose para levantar Odoo localmente.
- Ollama en ejecucion para los nodos que usan LLM.
- Un modelo local de Ollama, por ejemplo:

```bash
ollama pull qwen3:4b
```

El proyecto carga la configuracion desde archivos locales y/o el entorno de
ejecucion. Este README no documenta nombres ni valores de configuracion sensible;
usa los ejemplos del repositorio o la configuracion local del entorno donde se
despliegue.

## Instalacion Local

Desde la raiz del proyecto:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

En bash:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Ejecutar

### Backend Local

```bash
python api.py
```

La API queda disponible en:

- Frontend estatico: `http://localhost:8000/`
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

### Odoo, Backend, Postgres Y Ollama Con Docker

```bash
docker compose up --build
```

Servicios principales:

- Backend: `http://localhost:8000`
- Odoo: `http://localhost:8069`
- Ollama: `http://localhost:11434`
- Postgres: servicio interno `db`

El compose monta los addons desde `./odoo/addons` y reutiliza la cache local de
Ollama. Descarga el modelo en el host antes de levantar el stack.

### Bootstrap Inicial De Odoo

Con Odoo levantado:

```powershell
$env:PYTHONPATH=(Get-Location).Path
python .\scripts\bootstrap_odoo.py
```

El bootstrap:

- instala modulos base y addons custom;
- instala Helpdesk, CRM, Ventas, correo entrante y asistente virtual;
- crea productos presupuestables de referencia;
- crea contactos, tickets y correos demo;
- crea equipos, tipos, categorias, estados y etiquetas de Helpdesk;
- crea el usuario interno `Asistente Virtual`;
- configura parametros internos para que Odoo llame al backend;
- configura integracion Gmail si el entorno local la proporciona.

## Endpoints

### `GET /health`

```json
{"status":"ok"}
```

### `GET /`

Sirve `frontend.html`, una interfaz estatica sencilla para probar el backend.

### `POST /assistant/incoming-email`

Procesa un correo entrante y crea un ticket de Helpdesk.

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
  "final_text": "Ticket creado correctamente en Odoo con id 321 y tipo budget.",
  "reply_text": "",
  "route_name": null,
  "agent_name": null,
  "normalized_request": {
    "company_name": "ACME",
    "project_summary": "Solicitud de presupuesto CRM",
    "requirements": ["CRM", "automatizacion comercial"],
    "urgency": "media",
    "ticket_type": "budget"
  },
  "ticket_payload": {
    "team_name": "Presupuestos",
    "type_name": "Presupuesto",
    "category_name": "Consulta presupuesto"
  },
  "warnings": [],
  "error": null,
  "trace": ["incoming_email_received", "ticket_type_decided:budget", "ticket_created:321", "email_reply_skipped"]
}
```

### `POST /assistant/ticket-entry`

Primera respuesta para un ticket ya creado.

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

Respuesta resumida:

```json
{
  "ok": true,
  "route_name": "budget",
  "agent_name": null,
  "reply_text": "He detectado una solicitud de presupuesto...",
  "normalized_request": {},
  "quote_summary": {},
  "error": null,
  "trace": ["ticket_received", "route_decided:budget", "budget_waiting_ready_state"]
}
```

### `POST /assistant/discuss-message`

Procesa mensajes posteriores del chat Discuss.

```bash
curl -X POST http://localhost:8000/assistant/discuss-message \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": 100,
    "ticket_title": "Solicitud presupuesto CRM",
    "ticket_description": "Necesitamos CRM y automatizacion comercial.",
    "assistant_route_name": "budget",
    "channel_id": 7,
    "channel_name": "Ticket 100 - Asistente Virtual",
    "message_id": 12,
    "author_name": "Ana",
    "author_email": "ana@acme.com",
    "body": "Si, crealo",
    "recent_messages": [],
    "thread_id": "manual-discuss-7"
  }'
```

Respuesta resumida cuando confirma la creacion:

```json
{
  "ok": true,
  "route_name": "budget",
  "agent_name": "assistant_chat_agent",
  "reply_text": "Perfecto, marco el ticket como listo para generar el presupuesto.",
  "actions": [
    {"type": "mark_ticket_ready", "ticket_id": 100}
  ],
  "trace": ["discuss_message_received", "route_decided:budget", "budget_creation_confirmed", "response_built:discuss_orchestrator"]
}
```

### `POST /assistant/budget-from-ticket`

Crea o reutiliza un presupuesto en Odoo desde un ticket validado.

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
  "reply_text": "He creado un presupuesto inicial para ACME...",
  "sale_order_id": 55,
  "normalized_request": {
    "company_name": "ACME",
    "project_summary": "Solicitud presupuesto CRM",
    "requirements": ["crm", "automatizacion comercial"]
  },
  "quote_summary": {
    "sale_order_id": 55,
    "client_order_ref": "helpdesk-ticket-100",
    "total": 3000.0,
    "currency": "EUR"
  },
  "error": null,
  "trace": ["budget_ticket_received", "agent_completed:budget_agent"]
}
```

### `POST /assistant/sales-from-ticket`

Crea o reutiliza una oportunidad CRM desde un ticket validado.

```bash
curl -X POST http://localhost:8000/assistant/sales-from-ticket \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": 101,
    "title": "Mejorar pipeline comercial",
    "description": "Queremos organizar leads y seguimiento de oportunidades.",
    "partner_id": 12,
    "partner_name": "ACME",
    "partner_email": "ana@acme.com",
    "thread_id": "manual-sales-101"
  }'
```

Respuesta resumida:

```json
{
  "ok": true,
  "agent_name": "sales_agent",
  "reply_text": "He creado la oportunidad comercial en CRM...",
  "crm_lead_id": 77,
  "crm_summary": {
    "id": 77,
    "name": "ACME - Mejorar pipeline comercial",
    "type": "opportunity"
  },
  "error": null,
  "trace": ["sales_ticket_received", "agent_completed:sales_agent"]
}
```

## Tests

Tests rapidos sin Odoo real:

```powershell
python -m pytest -q tests/test_router.py tests/test_assistant_entry.py tests/test_assistant_email.py tests/test_assistant_discuss.py tests/test_assistant_sales.py tests/test_intake_partner_assignment.py tests/test_deepeval_eval.py tests/test_contract_validation.py tests/test_multi_model_eval_reporting.py
```

Excluir integracion:

```bash
python -m pytest -q -m "not integration"
```

Tests con Odoo real levantado y datos bootstrap:

```bash
python -m pytest -q -m integration
```

Por area:

```bash
python -m pytest -q tests/test_router.py
python -m pytest -q tests/test_assistant_entry.py tests/test_assistant_discuss.py tests/test_assistant_sales.py
python -m pytest -q tests/test_assistant_email.py tests/test_intake_partner_assignment.py
python -m pytest -q tests/test_intake_agent.py
python -m pytest -q tests/test_budget_agent.py
python -m pytest -q tests/test_deepeval_eval.py tests/test_contract_validation.py tests/test_multi_model_eval_reporting.py
```

## Calidad Y Formato

El proyecto configura Ruff, Mypy y Pytest en `pyproject.toml`.

```bash
python -m ruff format .
python -m ruff check . --fix
python -m mypy .
```

Pre-commit:

```bash
python -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Evaluaciones Multi-Modelo

DeepEval se usa en `shared/deepeval_eval.py` y los reportes agregados se generan
desde `evals/reporting.py`.

Ejecutar benchmark con modelos configurados en `evals/models.yaml`:

```bash
python -m evals.run_multi_model_eval
```

Ejecutar benchmark con modelos explicitos:

```bash
python -m evals.run_multi_model_eval \
  --cases evals/benchmark_cases.jsonl \
  --models qwen3:4b llama3.2 mistral \
  --out-dir evals/reports
```

La salida se guarda en `evals/reports/` como JSON detallado y Markdown
comparativo.

## Estructura Del Repositorio

```text
.
|-- api.py
|-- frontend.html
|-- agents/
|   |-- assistant_chat_agent/
|   |-- budget_agent/
|   |-- general_agent/
|   |-- intake_agent/
|   `-- sales_agent/
|-- orchestration/
|-- routing/
|-- shared/
|-- odoo/
|   |-- addons/
|   |-- api.py
|   |-- mcp_client.py
|   `-- odoo_mcp_server.py
|-- scripts/
|   `-- bootstrap_odoo.py
|-- tests/
|-- evals/
`-- docs/
```

## Troubleshooting

### `ModuleNotFoundError`

Activa el entorno virtual e instala dependencias:

```bash
python -m pip install -r requirements.txt
```

### El Backend No Conecta Con Odoo

Comprueba que Odoo este levantado, que la base de datos exista, que los addons
esten instalados y que la configuracion local apunte a la URL correcta tanto en
local como dentro de Docker.

### El LLM No Responde

Comprueba que Ollama este levantado y que el modelo este descargado:

```bash
ollama list
ollama run qwen3:4b
```

### Docker Compose Falla Al Iniciar Ollama

El servicio de inicializacion comprueba que el modelo ya exista en la cache local
montada. Descargalo antes de levantar Docker:

```bash
ollama pull qwen3:4b
```

### El Router Devuelve `discard`

El router exige senales claras. Para `budget` necesita intencion economica y
alcance. Para `sales` necesita intencion comercial, leads, oportunidades o
pipeline. Una incidencia de soporte sin intencion comercial se descarta para los
flujos de negocio automaticos.

### El Presupuesto No Encuentra Productos

Ejecuta el bootstrap o crea productos activos en Odoo con codigo interno. El
agente solo selecciona productos existentes en el catalogo real.

### El Presupuesto U Oportunidad No Se Crea Al Crear El Ticket

Es el comportamiento esperado. El registro de negocio se crea al confirmar desde
Discuss o al marcar el ticket como `Ready for next stage`.

Si no se crea al marcarlo como listo, revisa:

- que exista una ruta guardada `budget` o `sales`, o que el texto del ticket
  permita resolverla;
- que el ticket no tenga ya un registro de negocio asociado;
- que el backend pueda contactar con Odoo y Ollama;
- que el catalogo de productos exista para presupuestos;
- que CRM este instalado para oportunidades comerciales.

## Comandos Rapidos

```bash
python -m pip install -r requirements.txt
python api.py
docker compose up --build
python scripts/bootstrap_odoo.py
python -m pytest -q -m "not integration"
python -m evals.run_multi_model_eval
```
