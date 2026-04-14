from __future__ import annotations

import math
from collections import Counter
from statistics import mean
from typing import Any


def compute_rate(rows: list[dict[str, Any]], key: str) -> float:
    # Calcula el porcentaje de filas donde una clave es verdadera.
    # Ejemplo: success_rate, contract_pass_rate.
    if not rows:
        # Sin datos, la tasa es 0.
        return 0.0

    # Cuenta cuantas filas cumplen la condición.
    passed = sum(1 for row in rows if bool(row.get(key)))

    # Devuelve proporción: casos OK / casos totales.
    return passed / len(rows)


def compute_mean(rows: list[dict[str, Any]], key: str) -> float:
    # Calcula el promedio numérico de una métrica.
    # Ignora valores ausentes (None).
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    if not values:
        # Si no hay valores, no se puede promediar.
        return 0.0

    # Promedio clásico.
    return mean(values)


def compute_latency_percentiles(
    rows: list[dict[str, Any]], percentiles: tuple[int, ...] = (50, 95)
) -> dict[int, float]:
    # Ordena latencias para poder leer percentiles.
    latencies = sorted(float(row["latency_ms"]) for row in rows if row.get("latency_ms") is not None)
    if not latencies:
        # Si no hay latencias, devolvemos 0 para cada percentil pedido.
        return {percentile: 0.0 for percentile in percentiles}

    # Mapa final: percentil -> valor de latencia.
    results: dict[int, float] = {}
    for percentile in percentiles:
        # Posición del percentil en la lista ordenada.
        rank = math.ceil((percentile / 100) * len(latencies))

        # Blindaje de índice para no salir del rango.
        index = min(max(rank - 1, 0), len(latencies) - 1)

        # Guardamos el valor del percentil.
        results[percentile] = latencies[index]
    return results


def group_errors(rows: list[dict[str, Any]]) -> dict[str, int]:
    # Agrupa errores por tipo para entender fallos frecuentes.
    counter: Counter[str] = Counter()
    for row in rows:
        # Solo nos interesan filas con fallo.
        if row.get("ok"):
            continue

        # Si no viene tipificado, cae en "unknown".
        error_type = str(row.get("error_type") or "unknown")
        counter[error_type] += 1

    # Se devuelve dict normal para serializar más fácil.
    return dict(counter)


def summarize_model(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latency = compute_latency_percentiles(rows)

    # Only score rows where pipeline succeeded
    ok_rows = [r for r in rows if r.get("ok")]

    def safe_mean(values: Any) -> float:
        vals = [v for v in values if v is not None]
        return mean(vals) if vals else 0.0

    return {
        "total_cases": len(rows),
        "success_rate": compute_rate(rows, "ok"),
        "answer_relevancy_mean": safe_mean(r.get("answer_relevancy_score") for r in ok_rows),
        "geval_mean": safe_mean(r.get("geval_score") for r in ok_rows),
        "latency_p50_ms": latency[50],
        "latency_p95_ms": latency[95],
        "errors": {
            "total": sum(1 for r in rows if not r.get("ok")),
            "rate": 1.0 - compute_rate(rows, "ok"),
            "types": group_errors(rows),
        },
    }


def select_winner(model_summaries: dict[str, dict[str, Any]]) -> str:
    if not model_summaries:
        return ""
    ordered = sorted(
        model_summaries.items(),
        key=lambda item: (
            -float(item[1].get("success_rate", 0.0)),           # 1st: success rate (highest)
            -float(item[1].get("answer_relevancy_mean", 0.0)),  # 2nd: relevancy (highest)
            -float(item[1].get("geval_mean", 0.0)),             # 3rd: geval (highest)
            float(item[1].get("latency_p50_ms", 0.0)),          # 4th: latency (lowest)
            item[0],                                             # 5th: name (tiebreak)
        ),
    )
    return ordered[0][0]


def render_markdown_report(run_id: str, model_summaries: dict[str, dict[str, Any]], winner: str) -> str:
    lines = [
        f"# Evaluación multi-modelo ({run_id})",
        "",
        f"**Modelo recomendado:** {winner or 'N/A'}",
        "",
        "---",
        "",
        "## Métricas utilizadas",
        "",
        "Las dos métricas de calidad las ejecuta un modelo Ollama local actuando como juez.",
        "Solo se evalúan los casos en los que el pipeline completó sin errores.",
        "",
        "### 1. Answer Relevancy — Relevancia de la respuesta",
        "Mide si el texto de respuesta generado aborda de forma relevante la solicitud original del cliente.",
        "El juez LLM analiza el input (email o chat) y el output (presupuesto) y puntúa cuán bien",
        "el output responde a lo que el cliente pidió.",
        "",
        "- **Implementación:** DeepEval `AnswerRelevancyMetric`",
        "- **Escala:** 0.0 – 1.0 (mayor = más relevante)",
        "- **Umbral de aprobación:** ≥ 0.5",
        "- **Parámetros evaluados:** input del cliente → output del agente",
        "",
        "### 2. Quote Quality — Calidad del presupuesto (GEval)",
        "Evalúa si el output cumple los requisitos de un presupuesto ERP profesional.",
        "El criterio exacto que se pasa al juez es:",
        "",
        "> *The response is a professional sales quote or budget document written in Spanish.*",
        "> *It must mention at least one specific ERP module or service, include pricing information*",
        "> *(amounts in euros), and directly address the customer's stated needs from the input.*",
        "",
        "En otras palabras, el output debe:",
        "1. Estar redactado en español.",
        "2. Nombrar al menos un módulo o servicio ERP concreto.",
        "3. Incluir importes en euros.",
        "4. Responder directamente a la necesidad expresada por el cliente.",
        "",
        "- **Implementación:** DeepEval `GEval` con criterios personalizados",
        "- **Escala:** 0.0 – 1.0 (mayor = mayor calidad)",
        "- **Umbral de aprobación:** ≥ 0.5",
        "- **Parámetros evaluados:** input del cliente + output del agente",
        "",
        "### 3. Success Rate — Tasa de éxito del pipeline",
        "Proporción de casos en los que el pipeline completó la ejecución sin lanzar errores (`ok=true`).",
        "Los casos de entrada inválida (email sin cuerpo, chat sin mensaje) fallan por diseño",
        "y cuentan como error — reflejan la robustez del modelo ante inputs mal formados.",
        "",
        "- **Escala:** 0 % – 100 %",
        "- **Nota:** Answer Relevancy y GEval solo se calculan sobre los casos con `ok=true`.",
        "",
        "### 4. Latencia p50 / p95",
        "Tiempo de ejecución del pipeline completo (desde que se recibe el input hasta que se genera el presupuesto),",
        "medido en milisegundos.",
        "",
        "- **p50 (mediana):** La mitad de los casos son más rápidos que este valor.",
        "- **p95 (cola alta):** Solo el 5 % de los casos supera este valor; indica el peor caso habitual.",
        "",
        "### Criterio de selección del modelo ganador",
        "Se aplican los siguientes criterios en orden de prioridad (el primero que distingue gana):",
        "",
        "1. **Success Rate** mayor (más casos completados sin error).",
        "2. **Answer Relevancy** media mayor (respuestas más relevantes).",
        "3. **GEval** media mayor (presupuestos de mayor calidad).",
        "4. **Latencia p50** menor (pipeline más rápido).",
        "5. **Nombre del modelo** en orden alfabético (desempate final).",
        "",
        "---",
        "",
        "## Tabla comparativa",
        "",
        "| Modelo | Éxito | Relevancia | GEval | p50 ms | p95 ms | Errores |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for model, s in sorted(model_summaries.items()):
        lines.append(
            "| {model} | {success:.0%} | {rel:.3f} | {geval:.3f} | {p50:.0f} | {p95:.0f} | {err:.0%} |".format(
                model=model,
                success=float(s["success_rate"]),
                rel=float(s["answer_relevancy_mean"]),
                geval=float(s["geval_mean"]),
                p50=float(s["latency_p50_ms"]),
                p95=float(s["latency_p95_ms"]),
                err=float(s["errors"]["rate"]),
            )
        )

    lines += ["", "---", "", "## Errores por modelo", ""]
    for model, s in sorted(model_summaries.items()):
        lines.append(f"### {model}")
        error_types = s["errors"].get("types", {})
        if not error_types:
            lines.append("- Sin errores")
        else:
            for etype, count in sorted(error_types.items()):
                lines.append(f"- `{etype}`: {count} caso(s)")
        lines.append("")

    return "\n".join(lines) + "\n"
