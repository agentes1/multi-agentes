# Multi-agentes — Presupuestación automática con LangGraph

Sistema multi-agente que recibe solicitudes de clientes (email, chat, etc), las interpreta y genera un presupuesto estructurado. Construido con LangGraph y LangChain, pensado para conectarse a Odoo.

---

## Arquitectura

Entrada (email / API / webhook)
        ↓
    api.py  →  pipeline.py
                    ↓
            intake_agent          → normalized_request
                    ↓
            budget_agent          → quote_result + final_text
                    ↓
        (próximo) OdooService     → sale.order en Odoo

### Estructura de carpetas

multi-agentes/
├── agents/
│   ├── intake_agent/       # estado, grafo, nodos, dependencias
│   └── budget_agent/       # estado, grafo, nodos, dependencias
├── mcp/
│   └── mcp_servidor_precios.py   # servidor MCP con herramientas de pricing
├── schemas/
│   └── budget.py           # contratos de datos entre agentes (Pydantic)
├── services/
│   └── mcp_budget.py       # cliente MCP usado por el budget_agent
├── shared/
│   ├── catalog.py          # mapeo de requisitos a productos
│   ├── llm.py              # factoría de modelos LLM
│   ├── memory_store.py     # histórico de presupuestos por empresa
│   └── config.py           # variables de entorno
├── memory_data/
│   └── quote_memory.json   # persistencia local del histórico
├── tests/
│   ├── test_intake_agent.py
│   ├── test_budget_agent.py
│   └── test_api.py
├── api.py                  # endpoint REST (FastAPI)
├── pipeline.py             # orquestador: conecta los dos agentes
└── pyproject.toml

---

## Uso

### Arrancar la API

'''bash
python api.py
'''

Documentación interactiva disponible en `http://localhost:8000/docs`.

### Llamar al endpoint

'''bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "source_input": {
      "channel": "email",
      "from": "cliente@acme.com",
      "subject": "Solicitud presupuesto ERP",
      "body": "Somos Acme SL, necesitamos CRM y módulo de facturación con Odoo."
    }
  }'
'''

### Respuesta esperada

'''json
{
  "ok": true,
  "thread_id": "uuid",
  "normalized_request": {
    "company_name": "Acme SL",
    "requirements": ["crm", "presupuestos"],
    "urgency": "media"
  },
  "quote_result": {
    "total": 4500.0,
    "currency": "EUR"
  },
  "final_text": "Presupuesto preliminar para Acme SL..."
}
'''

### Códigos de respuesta

| Código | Significado |
|---|---|
| `200` | Presupuesto generado correctamente |
| `400` | Error de negocio (email vacío, sin productos reconocibles, MCP caído) |
| `422` | Error de validación (body del request mal formado) |

---

## Tests

'''bash
pytest tests/
'''

Cada agente tiene sus propios tests unitarios con mocks. Los tests de la API usan `httpx` con la app montada en memoria, sin necesidad de levantar el servidor.

---

## Flujo de datos interno

```
source_input (dict)
    → prepare_input_node     # normaliza canal (email/chat/etc)
    → extract_request_node   # LLM extrae JSON estructurado
    → validate_request_node  # comprueba campos mínimos (no bloqueante)
    → normalized_request

normalized_request (dict)
    → prepare_budget_node    # mapea requisitos a productos del catálogo
    → retrieve_memory_node   # recupera histórico del cliente
    → pricing_node           # llama al MCP para calcular precios
    → render_quote_node      # LLM redacta el presupuesto final
    → persist_memory_node    # guarda en histórico
    → quote_result + final_text
```

Los errores en cualquier nodo redirigen a un `error_node` que cierra el grafo limpiamente sin lanzar excepciones.

---

## Próximos pasos

- Conectar `OdooService` al pipeline para crear `sale.order` automáticamente
- Reemplazar datos mock del MCP por llamadas reales a Odoo
- Añadir listener de emails
- Implementar resto de agentes
- Modelo LLMs estudiados
