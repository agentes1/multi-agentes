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
- [API Reference](#api-reference)
- [Router semántico](#router-semantico)
- [Tests](#tests)
- [Calidad de código](#calidad-de-codigo)
- [Evaluación de modelos](#evaluacion-de-modelos)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Troubleshooting](#troubleshooting)
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

```
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

---

### Bootstrap de Odoo

Con Odoo levantado, ejecuta el script de inicialización **una sola vez** para configurar el sistema completo:

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
- Configura OAuth de Gmail si las variables están definidas en el entorno

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

Llamado por el addon `mail_inbox_input` al recibir un correo.

```bash
curl -X POST http://localhost:8000/assistant/incoming-email \
  -H "Content-Type: application/json" \
  -d '{
    "inbox_id": 1,
    "subject": "Solicitud de presupuesto",
    "email_from": "Ana <ana@acme.com>",
    "body": "Necesitamos implantar CRM y automatizacion comercial.",
    "thread_id": "email-1"
  }'
```

Respuesta:

```json
{
  "ok": true,
  "ticket_id": 321,
  "final_text": "He detectado que este ticket puede requerir presupuesto...",
  "reply_text": "He detectado que este ticket puede requerir presupuesto...",
  "route_name": "budget",
  "agent_name": null,
  "normalized_request": {
    "company_name": "ACME",
    "project_summary": "Solicitud de presupuesto CRM",
    "requirements": ["CRM", "automatizacion comercial"],
    "urgency": "media",
    "ticket_type": "budget"
  },
  "error": null,
  "trace": ["incoming_email_received", "ticket_created:321", "route_decided:budget"]
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
    "thread_id": "ticket-100"
  }'
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
    "thread_id": "discuss-7"
  }'
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
    "thread_id": "budget-100"
  }'
```

Respuesta:

```json
{
  "ok": true,
  "agent_name": "budget_agent",
  "reply_text": "He generado un presupuesto inicial en Odoo...",
  "sale_order_id": 55,
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

El router vive en `routing/semantic_router.py` y usa un enfoque híbrido en tres capas:

1. **Reglas de prioridad** (deterministas): detecta señales comerciales claras sin LLM.
2. **Coincidencia por keywords**: tokens normalizados sin stopwords.
3. **Similitud con utterances**: `difflib.SequenceMatcher` contra ejemplos de entrenamiento (55 % del score).
4. **Embeddings opcionales**: similitud coseno via Ollama (activables con `ROUTER_EMBEDDINGS_ENABLED=true`).

| Ruta | Señales que la activan |
|---|---|
| `budget` | presupuesto, precio, propuesta, implantación Odoo, CRM, ERP, formación, soporte mensual, desarrollo a medida |
| `sales` | ventas, pipeline, leads, oportunidades, seguimiento comercial |
| `discard` | saludos, pruebas, consultas generales sin acción clara |

---

## Tests

### Tests unitarios (sin Odoo real)

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

### Ejecutar tests estructurales

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

- `*.json` — resultados detallados por modelo y caso
- `*.md` — tabla comparativa markdown con ganador global

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

Asegúrate de tener el entorno virtual activo e instalar las dependencias:

```bash
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### El backend no conecta con Odoo

Verifica:

- Odoo está levantado en `http://localhost:8069` (local) o `http://web:8069` (Docker).
- `ODOO_BASE_URL`, `ODOO_DB`, `ODOO_USERNAME` y `ODOO_PASSWORD` son correctos.
- La base de datos existe y los addons están instalados.

### Ollama no responde

```bash
ollama list          # muestra los modelos descargados
ollama run qwen3:4b  # prueba el modelo manualmente
```

Revisa también `OLLAMA_MODEL` y `OLLAMA_BASE_URL`.

### Docker Compose falla por variables de entorno

El compose interpola credenciales desde el entorno de la shell. Exporta las variables o crea el archivo `.env` antes de ejecutar `docker compose up`.

### El router devuelve siempre `discard`

El router requiere **señales comerciales claras**. Para que clasifique como `budget` el texto debe contener al menos un término comercial (`presupuesto`, `precio`, `propuesta`) combinado con un término de alcance (`CRM`, `ERP`, `Odoo`, `implantación`, `ventas`, `automatización`).

### El presupuesto no se genera al mover el ticket

Verifica:

- Aparece una llamada a `POST /assistant/budget-from-ticket` en los logs del backend.
- El cambio de etapa escribe `kanban_state = "done"`.
- El ticket no tiene ya `assistant_budget_created` o `assistant_sale_order_id`.
- El catálogo tiene productos activos con `default_code`. Ejecuta el bootstrap si no los hay.

Códigos de producto de referencia creados por el bootstrap:

```text
crm | automatizacion_comercial | helpdesk | sales
implantacion_odoo | formacion | soporte_mensual | desarrollo_medida
```

### El presupuesto no se crea al crear un ticket manualmente

Es el comportamiento esperado. La creación manual de un ticket solo abre el chat de asistente y llama a `/assistant/ticket-entry`. El presupuesto se dispara únicamente cuando el ticket pasa a **Ready for next stage**.

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
