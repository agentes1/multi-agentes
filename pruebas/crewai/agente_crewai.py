from __future__ import annotations

import json
import sys
from pathlib import Path

from crewai import LLM, Agent, Crew, Process, Task
from crewai.mcp import MCPServerStdio

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent.parent
MCP_SERVER_PATH = PROJECT_ROOT / "mcp" / "mcp_servidor_precios.py"

llm = LLM(
    model="ollama/qwen2.5:3b",
    base_url="http://localhost:11434",
    temperature=0,
)


def build_crew(input_data: dict) -> Crew:
    if not MCP_SERVER_PATH.exists():
        raise FileNotFoundError(f"No existe el servidor MCP en esta ruta: {MCP_SERVER_PATH}")

    # Aquí uso la integración MCP recomendada por CrewAI en vez del adapter avanzado.
    # Así evito la ruta interna que te está intentando autoinstalar paquetes.
    local_mcp = MCPServerStdio(
        command=sys.executable,
        args=[str(MCP_SERVER_PATH)],
        cache_tools_list=True,
    )

    analyst = Agent(
        role="Analista de oportunidades",
        goal="Extraer requisitos de una solicitud comercial para preparar un presupuesto",
        backstory=(
            "Eres un analista comercial metódico. "
            "Lees solicitudes y las conviertes en requisitos funcionales claros."
        ),
        llm=llm,
        allow_delegation=True,
        verbose=True,
    )

    # En este agente engancho el MCP con mcps, que es el patrón recomendado.
    estimator = Agent(
        role="Generador de presupuestos",
        goal="Crear un borrador de presupuesto realista usando el catálogo MCP",
        backstory=(
            "Eres un perfil preventa técnico-comercial. "
            "Conviertes requisitos en un presupuesto claro y realista."
        ),
        llm=llm,
        mcps=[local_mcp],
        allow_delegation=True,
        verbose=True,
    )

    analysis_task = Task(
        description=f"""
Lee esta solicitud en JSON y genera un análisis en JSON.

SOLICITUD:
{json.dumps(input_data, ensure_ascii=False, indent=2)}

El JSON debe incluir exactamente estas claves:
- customer_name
- company_name
- summary
- requested_capabilities
- suggested_service_codes
- urgency
- missing_information

Reglas:
- Responde en español.
- No inventes datos que no estén en la solicitud.
- suggested_service_codes solo puede contener:
  crm_base, email_ai, quotation_ai, odoo_connector, dashboard
- Si algún dato no está claro, añádelo a missing_information.
""",
        expected_output="Un JSON válido con el análisis de la solicitud",
        agent=analyst,
    )

    budget_task = Task(
        description="""
A partir del análisis anterior, genera un presupuesto borrador en JSON.

Antes de cerrar el presupuesto, consulta las herramientas MCP disponibles para:
- listar servicios si lo necesitas
- recuperar detalle de los servicios sugeridos
- obtener el perfil del cliente si aplica
- calcular el presupuesto final

El JSON final debe incluir exactamente estas claves:
- project_title
- executive_summary
- included_services
- assumptions
- timeline_days
- subtotal_eur
- tax_percent
- total_eur
- next_questions
- status

Reglas:
- Escribe en español.
- Usa tax_percent=21.
- Si faltan datos, deja status="pendiente_revision".
- Basa los precios en la información obtenida desde MCP.
- included_services debe incluir nombre y precio de cada módulo.
""",
        expected_output="Un JSON válido con el presupuesto borrador",
        agent=estimator,
        context=[analysis_task],
    )

    return Crew(
        agents=[analyst, estimator],
        tasks=[analysis_task, budget_task],
        process=Process.sequential,
        memory=True,
        stream=True,
        verbose=True,
    )


if __name__ == "__main__":
    print(f"Proyecto raíz: {PROJECT_ROOT}")
    print(f"Servidor MCP: {MCP_SERVER_PATH}")

    input_data = {
        "customer_name": "Marta",
        "company_name": "BlueNova",
        "summary": (
            "Queremos automatizar la clasificación de emails, generar respuestas "
            "iniciales para preguntas frecuentes, crear presupuestos asistidos "
            "y conectar el flujo comercial con Odoo"
        ),
        "requested_capabilities": [
            "clasificación de emails",
            "respuestas FAQ",
            "presupuestos",
            "integración con Odoo",
        ],
        "urgency": "alta",
    }

    crew = build_crew(input_data)
    streaming = crew.kickoff()

    for chunk in streaming:
        print("\n=== STREAM CREWAI ===")
        print(chunk)

    print("\n\n=== RESULTADO FINAL CREWAI ===")
    print(streaming.result.raw)
