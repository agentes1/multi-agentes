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
    # Resume TODO lo importante de un modelo en una sola estructura.
    latency = compute_latency_percentiles(rows)
    return {
        # Cuántos casos se evaluaron para este modelo.
        "total_cases": len(rows),

        # Tasa de ejecución exitosa del pipeline.
        "success_rate": compute_rate(rows, "ok"),

        # Tasa de cumplimiento del contrato evaluado.
        "contract_pass_rate": compute_rate(rows, "contract_success"),

        # Promedio del score de DeepEval.
        "deepeval_score_mean": compute_mean(rows, "deepeval_score"),

        # Latencia mediana.
        "latency_p50_ms": latency[50],

        # Latencia en cola alta.
        "latency_p95_ms": latency[95],

        # Bloque de errores para diagnóstico rápido.
        "errors": {
            # Número total de casos fallidos.
            "total": sum(1 for row in rows if not row.get("ok")),

            # Proporción de error = 1 - success_rate.
            "rate": 1.0 - compute_rate(rows, "ok"),

            # Conteo por tipo de error.
            "types": group_errors(rows),
        },
    }


def select_winner(model_summaries: dict[str, dict[str, Any]]) -> str:
    # Elige ganador con criterio compuesto y ordenado.
    if not model_summaries:
        # Si no hay modelos, no hay ganador.
        return ""

    # Orden de prioridad:
    # 1) contract_pass_rate (más alto mejor)
    # 2) deepeval_score_mean (más alto mejor)
    # 3) latency_p50_ms (más bajo mejor)
    # 4) nombre de modelo (desempate estable)
    ordered = sorted(
        model_summaries.items(),
        key=lambda item: (
            -float(item[1].get("contract_pass_rate", 0.0)),
            -float(item[1].get("deepeval_score_mean", 0.0)),
            float(item[1].get("latency_p50_ms", 0.0)),
            item[0],
        ),
    )

    # El primero del ordenado es el ganador.
    return ordered[0][0]


def render_markdown_report(run_id: str, model_summaries: dict[str, dict[str, Any]], winner: str) -> str:
    # Arma cabecera del reporte en Markdown.
    # Incluye resumen y tabla base.
    header = [
        f"# Multi-model LLM Evaluation ({run_id})",
        "",
        "## Resumen",
        f"- Modelo ganador (criterio compuesto): **{winner or 'N/A'}**",
        "",
        "## Tabla comparativa",
        "",
        "| Modelo | Contract pass | DeepEval mean | Success rate | p50 ms | p95 ms | Error rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    # Filas de la tabla comparativa por modelo.
    rows: list[str] = []
    for model, summary in sorted(model_summaries.items()):
        rows.append(
            "| {model} | {contract:.2%} | {deepeval:.3f} | {success:.2%} | {p50:.1f} | {p95:.1f} | {error_rate:.2%} |".format(
                model=model,
                contract=float(summary["contract_pass_rate"]),
                deepeval=float(summary["deepeval_score_mean"]),
                success=float(summary["success_rate"]),
                p50=float(summary["latency_p50_ms"]),
                p95=float(summary["latency_p95_ms"]),
                error_rate=float(summary["errors"]["rate"]),
            )
        )

    # Sección de detalle de errores por modelo.
    details = ["", "## Errores por modelo", ""]
    for model, summary in sorted(model_summaries.items()):
        details.append(f"### {model}")
        error_types = summary["errors"].get("types", {})
        if not error_types:
            # Caso limpio: no hubo fallos.
            details.append("- Sin errores")
            continue

        # Lista de errores y su frecuencia.
        for error_type, count in sorted(error_types.items()):
            details.append(f"- {error_type}: {count}")

    # Une todo y garantiza salto de línea final.
    return "\n".join(header + rows + details) + "\n"
