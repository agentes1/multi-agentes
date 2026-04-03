# Multi-agentes: guía completa desde cero

Proyecto Python con arquitectura multi-agente para transformar una solicitud de cliente (email/chat) en un presupuesto estructurado y un texto final listo para enviar.

Incluye:
- API REST con FastAPI.
- Dos agentes en cadena (`intake_agent` y `budget_agent`) orquestados con LangGraph.
- Integración MCP para pricing.
- Tests clásicos (`pytest`) y evaluación de calidad con DeepEval (https://deepeval.com).

## 1) Requisitos previos

- Windows, macOS o Linux.
- Python 3.11+.
- Git.
- (Opcional para flujo completo real) Ollama en ejecución con el modelo configurado (`llama3.1` por defecto).

## 2) Instalación desde cero

Desde la carpeta donde quieras trabajar:

```bash
git clone https://github.com/agentes1/multi-agentes.git
cd multi-agentes
```

Crear y activar entorno virtual.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instalar dependencias:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 3) Arrancar la API

```bash
python api.py
```

API docs: http://localhost:8000/docs

Healthcheck:

```bash
curl http://localhost:8000/health
```

Respuesta esperada:

```json
{"status":"ok"}
```

## 4) Usar el endpoint principal

### Ejemplo de request

```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "source_input": {
      "channel": "email",
      "from": "cliente@acme.com",
      "subject": "Solicitud presupuesto ERP",
      "body": "Somos Acme SL, necesitamos CRM y facturación."
    }
  }'
```

### Ejemplo de respuesta

```json
{
  "ok": true,
  "thread_id": "5be2f8f9-3f9f-4d0f-8cb3-93fc5f51c5dc",
  "stage": null,
  "error": null,
  "validation_notes": [],
  "normalized_request": {
    "company_name": "Acme SL",
    "requirements": ["crm", "presupuestos"],
    "urgency": "media"
  },
  "quote_result": {
    "company_name": "Acme SL",
    "subtotal": 3000.0,
    "discount": 300.0,
    "total": 2700.0,
    "currency": "EUR"
  },
  "final_text": "Presupuesto preliminar para Acme SL..."
}
```

## 5) Ejecutar tests clásicos

```bash
python -m pytest tests -q
```

Estos tests validan:
- Flujo de `intake_agent`.
- Errores controlados de `budget_agent`.
- Endpoint API.

## 6) DeepEval (oficial de deepeval.com)

Este proyecto usa el paquete oficial `deepeval` y una métrica determinista local (`PipelineContractMetric`) para evitar dependencia de API keys externas.

Archivo de integración: [shared/deepeval_eval.py](shared/deepeval_eval.py)

Qué valida esta métrica:
- Si `ok=true`:
  - estructura básica de `quote_result`;
  - coherencia numérica (`subtotal - discount == total`);
  - que exista `final_text`.
- Si `ok=false`:
  - que exista `error`.

### Ejecutar solo evaluación DeepEval

```bash
python -m pytest tests/test_deepeval_eval.py -q
```

### Caso de ejemplo DeepEval

Ver [tests/test_deepeval_eval.py](tests/test_deepeval_eval.py), donde:
- se crea un `LLMTestCase` desde input + resultado de pipeline;
- se aplica `PipelineContractMetric`;
- se ejecuta `assert_test(...)`.

## 7) Estructura de alto nivel

```text
Entrada (email/chat)
  -> api.py
  -> pipeline.py
       -> intake_agent (normaliza solicitud)
       -> budget_agent (genera quote_result + final_text)
```

## 8) Solución de problemas

1. `ModuleNotFoundError` al ejecutar tests
   - Asegura entorno activo y reinstala dependencias:
   - `python -m pip install -r requirements.txt`

2. Error de conexión de modelo local (Ollama)
   - Verifica que Ollama esté levantado y que exista el modelo configurado.

3. Error 400 en `/process`
   - Es un error de negocio (ejemplo: entrada vacía o fallo MCP). Revisa `detail.error` en la respuesta.

## 9) Comandos rápidos

```bash
# instalar
python -m pip install -r requirements.txt

# arrancar API
python api.py

# tests clásicos
python -m pytest tests -q

# evals DeepEval
python -m pytest tests/test_deepeval_eval.py -q

# benchmark multi-modelo (ejemplo)
python -m evals.run_multi_model_eval --cases evals/benchmark_cases.jsonl --models qwen2.5 qwen3 llama3 --out-dir evals/reports
```

## 10) Benchmark de modelos (Qwen/Llama)

Para comparar modelos en el pipeline real con métricas de calidad + latencia:

```bash
python -m evals.run_multi_model_eval --cases evals/benchmark_cases.jsonl --models qwen2.5 qwen3 llama3 --out-dir evals/reports
```

Se generan dos artefactos:
- JSON detallado con resultados por caso y agregados por modelo.
- Markdown con tabla comparativa y ganador.

Guía completa de metodología e interpretación:
- [docs/model_evaluation_guide.md](docs/model_evaluation_guide.md)
