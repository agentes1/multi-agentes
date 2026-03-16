from __future__ import annotations

# streaming + memoria compartida entre agentes dentro del ecosistema LangChain.
# LangGraph se apoya en un grafo con estado compartido, así que cada nodo
# puede leer lo que dejó el anterior y escribir su parte del trabajo.
import json
from typing import Literal, NotRequired, TypedDict

import requests
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field


# entrada de tipo pseudo-email
class EmailInput(BaseModel):
    from_email: str
    to_email: str
    subject: str
    body: str


# Este primer esquema representa lo que extrae el agente analizador.
class BudgetRequestAnalysis(BaseModel):
    language: str = Field(description="Idioma detectado, por ejemplo es o en")
    customer_name: str | None = Field(default=None, description="Nombre del cliente si aparece")
    company_name: str | None = Field(default=None, description="Empresa del cliente si aparece")
    request_type: Literal["automatizacion", "ia", "consultoria", "soporte", "otro"]
    summary: str = Field(description="Resumen breve en español")
    requested_services: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    urgency: Literal["baja", "media", "alta"]
    needs_follow_up: bool
    missing_info: list[str] = Field(default_factory=list)


# Cada línea del presupuesto se representa por separado
class BudgetLine(BaseModel):
    concept: str
    quantity: int
    unit_price_eur: float
    subtotal_eur: float
    notes: str


# Salida final
class BudgetOutput(BaseModel):
    customer_name: str | None = None
    company_name: str | None = None
    project_title: str
    project_summary: str
    lines: list[BudgetLine] = Field(default_factory=list)
    subtotal_eur: float
    tax_percent: float
    tax_amount_eur: float
    total_eur: float
    assumptions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    status: Literal["borrador", "pendiente_revision"]


# Este TypedDict es el estado compartido del grafo.
# el analizador escribe su salida, el nodo de memoria la complementa,
# y el generador de presupuesto la reutiliza después.
class AgentState(TypedDict):
    email: EmailInput
    analysis: NotRequired[dict]
    customer_memory: NotRequired[dict]
    pricing_data: NotRequired[list[dict]]
    budget: NotRequired[dict]
    trace: NotRequired[list[str]]


# LangChain documenta streaming en sus chat models mediante stream/invoke;
llm = ChatOllama(
    model="qwen2.5:3b",
    base_url="http://localhost:11434",
    temperature=0,
)

analysis_llm = llm.with_structured_output(BudgetRequestAnalysis)
budget_llm = llm.with_structured_output(BudgetOutput)

# Checkpointer en memoria para mantener estado por thread_id.
checkpointer = InMemorySaver()

# Memoria larga simple
LONG_TERM_MEMORY: dict[str, dict] = {}


def append_trace(state: AgentState, message: str) -> list[str]:
    current = state.get("trace", [])
    return current + [message]


def load_customer_memory(state: AgentState) -> AgentState:
    # Este nodo no llama al LLM. Su único papel es recuperar memoria previa del cliente.
    email = state["email"]
    customer_key = email.from_email.lower()

    memory = LONG_TERM_MEMORY.get(
        customer_key,
        {
            "known_services": [],
            "last_company_name": None,
            "last_summary": None,
        },
    )

    return {
        "customer_memory": memory,
        "trace": append_trace(state, f"Memoria cargada para {customer_key}"),
    }


def analyze_email(state: AgentState) -> AgentState:
    # Aquí actúa el primer "agente": interpreta el correo y lo convierte
    email = state["email"]
    customer_memory = state.get("customer_memory", {})

    prompt = f"""
Eres un agente analizador de oportunidades comerciales.

Tu tarea es leer el email y devolver únicamente la estructura solicitada.

Contexto previo del cliente:
{json.dumps(customer_memory, ensure_ascii=False, indent=2)}

Reglas:
- Resume en español
- No inventes datos
- request_type debe ser: automatizacion, ia, consultoria, soporte, otro
- requested_services debe contener servicios concretos detectados
- requirements debe contener requisitos concretos si aparecen
- needs_follow_up debe ser true si faltan datos importantes

EMAIL:
From: {email.from_email}
To: {email.to_email}
Subject: {email.subject}

Body:
{email.body}
"""

    analysis = analysis_llm.invoke(prompt)

    return {
        "analysis": analysis.model_dump(),
        "trace": append_trace(state, "Email analizado por el agente analizador"),
    }


def query_mcp_price(service_name: str) -> dict:
    # Esta función es el puente más simple entre el flujo LangGraph y el servidor MCP.
    # Para una PoC es suficiente y fácil de depurar.
    # La llamada se hace contra el servidor que has levantado en el otro archivo.
    try:
        # Ejemplo corto y práctico.
        response = requests.post(
            "http://localhost:8000/mcp/tool/get_service_price",
            json={"service_name": service_name},
            timeout=5,
        )
        response.raise_for_status()
        return response.json()
    except Exception:
        return {
            "found": False,
            "service_name": service_name,
            "base_price": 0,
            "description": "No se pudo consultar el servicio en el servidor MCP",
        }


def enrich_with_pricing(state: AgentState) -> AgentState:
    analysis = state["analysis"]
    requested_services = analysis.get("requested_services", [])

    pricing_data = []
    service_map = {
        "consultoría": "consultoria",
        "consultoria": "consultoria",
        "automatización": "automatizacion_simple",
        "automatizacion": "automatizacion_simple",
        "clasificación de emails": "clasificacion_emails",
        "clasificacion de emails": "clasificacion_emails",
        "respuestas ia": "respuestas_ia",
        "respuestas con ia": "respuestas_ia",
        "integración api": "integracion_api",
        "integracion api": "integracion_api",
    }

    for service in requested_services:
        normalized = service_map.get(service.strip().lower())
        if normalized:
            pricing_data.append(query_mcp_price(normalized))

    return {
        "pricing_data": pricing_data,
        "trace": append_trace(state, "Precios consultados vía servidor MCP"),
    }


def build_budget(state: AgentState) -> AgentState:
    # Este es el segundo "agente": usa el análisis previo, la memoria del cliente
    # y la información económica externa para construir el presupuesto.
    # no repetimos el trabajo del primer nodo, sino que reaprovechamos su salida.
    email = state["email"]
    analysis = state["analysis"]
    customer_memory = state.get("customer_memory", {})
    pricing_data = state.get("pricing_data", [])

    prompt = f"""
Eres un agente generador de presupuestos.

Debes devolver únicamente la estructura solicitada.
Estás generando un presupuesto borrador, no definitivo.

EMAIL ORIGINAL:
From: {email.from_email}
To: {email.to_email}
Subject: {email.subject}

Body:
{email.body}

ANÁLISIS DEL AGENTE ANTERIOR:
{json.dumps(analysis, ensure_ascii=False, indent=2)}

MEMORIA PREVIA DEL CLIENTE:
{json.dumps(customer_memory, ensure_ascii=False, indent=2)}

PRECIOS CONSULTADOS EXTERNAMENTE:
{json.dumps(pricing_data, ensure_ascii=False, indent=2)}

Reglas:
- Escribe todo en español
- Usa tax_percent = 21
- Calcula subtotal, IVA y total correctamente
- Si faltan datos relevantes, status = pendiente_revision
- Si hay precios externos disponibles, úsalos como base
- No inventes integraciones complejas
- Mantén el presupuesto simple
"""

    budget = budget_llm.invoke(prompt)

    return {
        "budget": budget.model_dump(),
        "trace": append_trace(state, "Presupuesto generado por el agente presupuestador"),
    }


def save_customer_memory(state: AgentState) -> AgentState:
    # Este nodo actualiza una memoria sencilla de largo plazo.
    # La guardamos por email del cliente.
    email = state["email"]
    analysis = state["analysis"]

    customer_key = email.from_email.lower()
    previous = LONG_TERM_MEMORY.get(
        customer_key,
        {
            "known_services": [],
            "last_company_name": None,
            "last_summary": None,
        },
    )

    merged_services = list(
        {
            *previous.get("known_services", []),
            *analysis.get("requested_services", []),
        }
    )

    LONG_TERM_MEMORY[customer_key] = {
        "known_services": merged_services,
        "last_company_name": analysis.get("company_name") or previous.get("last_company_name"),
        "last_summary": analysis.get("summary"),
    }

    return {"trace": append_trace(state, "Memoria de largo plazo actualizada")}


# Construimos el grafo.
graph_builder = StateGraph(AgentState)

# Añadimos nodos. Cada nodo hace una responsabilidad concreta.
graph_builder.add_node("load_customer_memory", load_customer_memory)
graph_builder.add_node("analyze_email", analyze_email)
graph_builder.add_node("enrich_with_pricing", enrich_with_pricing)
graph_builder.add_node("build_budget", build_budget)
graph_builder.add_node("save_customer_memory", save_customer_memory)

# Definimos el orden del flujo.
graph_builder.add_edge(START, "load_customer_memory")
graph_builder.add_edge("load_customer_memory", "analyze_email")
graph_builder.add_edge("analyze_email", "enrich_with_pricing")
graph_builder.add_edge("enrich_with_pricing", "build_budget")
graph_builder.add_edge("build_budget", "save_customer_memory")
graph_builder.add_edge("save_customer_memory", END)

# Compilamos con checkpointer para tener estado asociado a un thread_id y poder continuar.
graph = graph_builder.compile(checkpointer=checkpointer)


def run_with_streaming(email: EmailInput, thread_id: str = "demo-thread") -> dict:
    # Aquí aplicamos STREAMING.
    # En vez de esperar al final, vamos viendo cómo avanza el flujo nodo a nodo.
    # final_state = None

    for event in graph.stream(
        {"email": email},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="updates",
    ):
        print("\n[STREAM EVENT]")
        print(json.dumps(event, ensure_ascii=False, indent=2, default=str))
        # final_state = event

    # Después del streaming, recuperamos el estado consolidado.
    snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})

    return snapshot.values


if __name__ == "__main__":
    # Primer email del cliente.
    fake_email_1 = EmailInput(
        from_email="cliente@empresa.com",
        to_email="presupuestos@tuempresa.com",
        subject="Queremos automatizar emails de soporte",
        body=(
            "Hola, soy Marta de BlueNova. "
            "Queremos clasificar emails de clientes automáticamente "
            "y generar una primera respuesta con IA para consultas frecuentes. "
            "Buscamos una propuesta sencilla para empezar este mes."
        ),
    )

    result_1 = run_with_streaming(fake_email_1, thread_id="cliente-bluenova")

    print("\n=== RESULTADO FINAL PRIMERA EJECUCIÓN ===")
    print(json.dumps(result_1, ensure_ascii=False, indent=2, default=str))

    # Segunda ejecución del mismo cliente para comprobar memoria entre ejecuciones.
    fake_email_2 = EmailInput(
        from_email="cliente@empresa.com",
        to_email="presupuestos@tuempresa.com",
        subject="Añadimos también integración API",
        body=(
            "Hola de nuevo. Además de lo anterior, nos interesa una integración básica "
            "con nuestra API interna para registrar tickets."
        ),
    )

    result_2 = run_with_streaming(fake_email_2, thread_id="cliente-bluenova")

    print("\n=== RESULTADO FINAL SEGUNDA EJECUCIÓN ===")
    print(json.dumps(result_2, ensure_ascii=False, indent=2, default=str))

    print("\n=== MEMORIA DE LARGO PLAZO GUARDADA ===")
    print(json.dumps(LONG_TERM_MEMORY, ensure_ascii=False, indent=2, default=str))
