# Multi-agentes

Backend Python multi-agente integrado con Odoo 18 para clasificar solicitudes de clientes, crear tickets de helpdesk y generar presupuestos comerciales en Odoo.

El flujo actual no usa un endpoint generico `/process`: Odoo llama a tres endpoints especificos del backend:

1. `/assistant/incoming-email`: procesa correos entrantes guardados por Odoo.
2. `/assistant/ticket-entry`: procesa tickets de helpdesk ya creados.
3. `/assistant/discuss-message`: procesa mensajes posteriores en el chat de Discuss.

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
- `agents/intake_agent/`: convierte correos/chats en tickets de helpdesk.
- `agents/budget_agent/`: crea contactos, presupuestos y lineas de venta en Odoo.
- `agents/general_agent/`: respuesta fija para mensajes descartados o no accionables.
- `odoo/api_wrapper.py`: cliente XML-RPC para modelos de Odoo.
- `odoo/odoo_mcp_server.py` y `odoo/mcp_client.py`: tools locales tipo MCP para catalogo, clientes y presupuestos.
- `odoo/addons/`: addons Odoo incluidos o adaptados para helpdesk, correo entrante y asistente virtual.

## 2. Flujo actual

### 2.1 Correo entrante

1. Odoo recibe un correo mediante `fetchmail`/Gmail.
2. El addon `mail_inbox_input` crea un `mail.inbox.message`.
3. Al crear el registro, el addon llama a `POST /assistant/incoming-email`.
4. `IncomingEmailOrchestrator` adapta el correo a `source_input`.
5. `intake_agent` ejecuta este grafo:
   - `prepare_input_node`: normaliza email/chat a texto.
   - `extract_request_node`: pide al LLM un JSON estructurado.
   - `prepare_ticket_node`: mapea tipo, equipo, categoria, prioridad y etiquetas.
   - `create_ticket_node`: crea `helpdesk.ticket` en Odoo.
6. Al crearse el ticket, el addon `helpdesk_virtual_assistant` abre un chat en Discuss y continua el flujo de ticket.

### 2.2 Ticket nuevo en Helpdesk

1. Odoo crea un `helpdesk.ticket`.
2. `helpdesk_virtual_assistant` abre un chat `Ticket <id> - Asistente Virtual`.
3. El addon publica un primer mensaje fijo de recepcion.
4. El addon llama a `POST /assistant/ticket-entry`.
5. `TicketEntryOrchestrator` construye texto enrutable y ejecuta `routing.semantic_router.router`.
6. Si la ruta es `budget`, se ejecuta `budget_agent`.
7. Si la ruta es `discard`, responde `general_agent`.

### 2.3 Mensajes posteriores en Discuss

1. El usuario escribe en el chat de Discuss abierto para el ticket.
2. La extension de `mail.message` detecta canales con formato `Ticket <id> - Asistente Virtual`.
3. Ignora mensajes escritos por el propio asistente para evitar bucles.
4. Llama a `POST /assistant/discuss-message`.
5. `DiscussMessageOrchestrator` enruta solo el mensaje nuevo, no el titulo historico del ticket.
6. Si el mensaje pide presupuesto, ejecuta `budget_agent`; si no, devuelve fallback general o no publica nada util.

### 2.4 Presupuestos

Cuando una entrada llega a `budget_agent`, el grafo ejecuta:

1. `prepare_budget_node`: busca productos reales de Odoo que coincidan con los requisitos detectados.
2. `ensure_partner_node`: obtiene o crea el contacto de la empresa.
3. `create_odoo_quote_node`: crea un `sale.order` y sus lineas.
4. `compose_budget_reply_node`: redacta una respuesta final con LLM. Si el LLM falla, usa una respuesta fallback.

El resultado incluye `quote_summary` con `sale_order_id`, productos, lineas, subtotal, total y moneda.

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
- configura URLs internas para ticket entry, Discuss e incoming email;
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
  "final_text": "Ticket creado correctamente en Odoo con id 321 y tipo budget.",
  "normalized_request": {},
  "ticket_payload": {},
  "warnings": [],
  "error": null,
  "trace": ["incoming_email_received", "ticket_type_decided:budget", "ticket_created:321"]
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
  "agent_name": "budget_agent",
  "reply_text": "Hola ACME...",
  "normalized_request": {},
  "quote_summary": {},
  "error": null,
  "trace": ["ticket_received", "route_decided:budget", "budget_request_prepared", "agent_completed:budget_agent"]
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
  tests/test_deepeval_eval.py
```

En PowerShell:

```powershell
python -m pytest -q tests/test_router.py tests/test_assistant_entry.py tests/test_assistant_email.py tests/test_assistant_discuss.py tests/test_deepeval_eval.py
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

# Orquestadores de API actuales
python -m pytest -q tests/test_assistant_entry.py tests/test_assistant_email.py tests/test_assistant_discuss.py

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
│   ├── intake_agent/
│   └── support_agent/
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

`budget_agent` busca productos reales de Odoo por texto y `default_code`. Ejecuta el bootstrap o crea productos con codigos como:

- `crm`
- `automatizacion_comercial`
- `helpdesk`
- `sales`
- `implantacion_odoo`
- `formacion`
- `soporte_mensual`
- `desarrollo_medida`

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
python -m pytest -q tests/test_router.py tests/test_assistant_entry.py tests/test_assistant_email.py tests/test_assistant_discuss.py tests/test_deepeval_eval.py

# Tests de integracion
python -m pytest -q -m integration

# Benchmark modelos
python -m evals.run_multi_model_eval
```
