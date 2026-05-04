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

### 6.3 Bootstrap inicial de Odoo

Con Odoo levantado, ejecuta:

```powershell
$env:PYTHONPATH=(Get-Location).Path
python .\scripts\bootstrap_odoo.py
```

El bootstrap:

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

## 9. Tests

### 9.1 Tests rapidos sin Odoo real

Estos tests usan fakes/mocks y sirven para validar router, orquestadores HTTP y utilidades de evaluacion:

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

Aviso: `tests/test_api.py` hay que modificarlo o eliminarlo

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

- `AnswerRelevancyMetric`;
- `GEval` con criterio de calidad de presupuesto;
- modelo evaluador local mediante Ollama.

Ejecutar tests estructurales de DeepEval:

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

Salida:

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

Activa el entorno virtual e instala dependencias:

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

El router solo tiene rutas `budget` y `discard`. Para que algo sea presupuesto debe contener señales comerciales claras, por ejemplo `presupuesto`, `precio`, `propuesta`, junto a alcance como `CRM`, `Odoo`, `ERP`, `implantacion`, `ventas` o `automatizacion`.

### El presupuesto no encuentra productos

`budget_agent` obtiene el catalogo real con `list_catalog()` y el LLM elige ids de producto de esa lista. Ejecuta el bootstrap o crea productos activos con `default_code`, por ejemplo:

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
