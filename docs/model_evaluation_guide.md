# Guia de evaluacion de modelos LLM

Este documento explica como comparar modelos (por ejemplo `qwen2.5`, `qwen3`, `llama3`) en este proyecto usando el pipeline real y DeepEval.

## Objetivo

Comparar modelos en tres dimensiones:

1. Calidad de salida estructurada y contrato del pipeline.
2. Robustez operativa (errores y tasa de exito).
3. Rendimiento (latencia p50/p95).

## Que se evalua exactamente

La evaluacion usa `PipelineContractMetric` y datos reales de entrada (`source_input`) pasando por `run_pipeline`.

### Metricas por modelo

1. `contract_pass_rate`
- Porcentaje de casos donde el contrato del pipeline pasa.
- Se valida estructura, consistencia de totales y shape de error.

2. `deepeval_score_mean`
- Promedio del score de la metrica DeepEval (`PipelineContractMetric`).

3. `success_rate`
- Porcentaje de casos con `ok=true` en `run_pipeline`.

4. `latency_p50_ms`
- Latencia mediana por caso.

5. `latency_p95_ms`
- Latencia en cola alta (peor caso habitual).

6. `errors.total`, `errors.rate`, `errors.types`
- Conteo y clasificacion de errores por tipo.

## Dataset de benchmark

Archivo: `evals/benchmark_cases.jsonl`

Formato por linea:

```json
{"case_id":"email_ok_001","thread_id":"eval-email-001","source_input":{"channel":"email","from":"cliente@acme.com","subject":"Presupuesto CRM","body":"Necesitamos CRM y facturacion"},"tags":["happy_path"]}
```

Campos:

1. `case_id`: identificador unico.
2. `thread_id`: identificador de trazabilidad.
3. `source_input`: entrada original del pipeline.
4. `tags`: etiquetas opcionales para segmentar resultados.

## Ejecutar benchmark multi-modelo

Desde la raiz del repo:

```bash
python -m evals.run_multi_model_eval --cases evals/benchmark_cases.jsonl --models qwen2.5 qwen3 llama3 --out-dir evals/reports
```

Salida esperada:

1. Reporte JSON en `evals/reports/multi_model_eval_YYYYMMDD_HHMMSS.json`.
2. Reporte Markdown en `evals/reports/multi_model_eval_YYYYMMDD_HHMMSS.md`.
3. Mensaje de ganador global en consola.

## Regla de ganador

El ganador se selecciona por este orden:

1. Mayor `contract_pass_rate`.
2. Mayor `deepeval_score_mean`.
3. Menor `latency_p50_ms`.
4. Desempate alfabetico por nombre de modelo.

## Como interpretar resultados

1. Si un modelo gana en `deepeval_score_mean` pero falla en `contract_pass_rate`, no es ideal para produccion.
2. Si dos modelos empatan en calidad, elige el de mejor `latency_p50_ms` y menor `errors.rate`.
3. Repite benchmark con dataset mas grande antes de decision final.

## Buenas practicas

1. No mezclar datasets entre corridas cuando compares modelos.
2. Fijar la misma configuracion de entorno para todos los modelos.
3. Ejecutar al menos 2-3 corridas y promediar.
4. Versionar el dataset de benchmark cuando cambie.

## Extensiones recomendadas

1. Añadir metrica de coste por token si usas proveedor con billing.
2. Añadir slicing por tags (`happy_path`, `invalid_input`, etc.).
3. Añadir comparativa temporal para detectar regresiones por version de modelo.
