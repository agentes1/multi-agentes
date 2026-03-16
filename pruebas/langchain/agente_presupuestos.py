from __future__ import annotations

from typing import Literal

from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

# 1) ENTRADA: pseudo email


class EmailInput(BaseModel):
    from_email: str
    to_email: str
    subject: str
    body: str


# 2) SALIDA INTERMEDIA: análisis del correo para presupuesto


class BudgetRequestAnalysis(BaseModel):
    language: str = Field(description="Idioma detectado, por ejemplo es o en")
    customer_name: str | None = Field(
        default=None, description="Nombre del cliente si se puede inferir del correo"
    )
    company_name: str | None = Field(default=None, description="Empresa del cliente si se menciona")
    request_type: Literal[
        "desarrollo_web", "automatizacion", "ia", "soporte", "consultoria", "otro"
    ]
    summary: str = Field(description="Resumen breve en español")
    project_description: str = Field(
        description="Descripción corta del proyecto pedida por el cliente"
    )
    requested_services: list[str] = Field(
        default_factory=list, description="Lista de servicios solicitados"
    )
    detected_requirements: list[str] = Field(
        default_factory=list, description="Requisitos detectados en el email"
    )
    estimated_complexity: Literal["baja", "media", "alta"]
    urgency: Literal["baja", "media", "alta"]
    has_budget_hint: bool = Field(description="True si el cliente menciona presupuesto o rango")
    budget_hint: str | None = Field(
        default=None, description="Rango o pista presupuestaria si aparece en el email"
    )
    deadline_hint: str | None = Field(
        default=None, description="Fecha o plazo si aparece en el email"
    )
    needs_follow_up: bool = Field(
        description="True si faltan datos relevantes para un presupuesto real"
    )
    missing_info: list[str] = Field(
        default_factory=list, description="Datos faltantes para afinar el presupuesto"
    )


# 3) SALIDA FINAL: pseudopresupuesto


class BudgetLine(BaseModel):
    concept: str
    description: str
    quantity: int = 1
    unit_price_eur: float
    subtotal_eur: float


class BudgetOutput(BaseModel):
    customer_name: str | None = None
    company_name: str | None = None
    project_title: str
    project_summary: str
    scope_items: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    timeline_estimate: str
    lines: list[BudgetLine] = Field(default_factory=list)
    subtotal_eur: float
    tax_percent: float
    tax_amount_eur: float
    total_eur: float
    notes: list[str] = Field(default_factory=list)
    status: Literal["borrador", "pendiente_revision", "listo_para_enviar"]


# 4) MODELO OLLAMA
#    Puedes cambiar a:
#    - qwen2.5:3b
#    - llama3.2:3b
#    - gemma3:4b

llm = ChatOllama(
    model="qwen2.5:3b",
    base_url="http://localhost:11434",
    temperature=0,
)

analysis_llm = llm.with_structured_output(BudgetRequestAnalysis)
budget_llm = llm.with_structured_output(BudgetOutput)


# 5) PASO 1: ANALIZAR EL EMAIL


def analyze_email_for_budget(email: EmailInput) -> BudgetRequestAnalysis:
    prompt = f"""
Eres un asistente experto en preventa y generación de presupuestos.

Tu tarea es analizar un email de cliente y devolver ÚNICAMENTE
la estructura solicitada.

Reglas:
- Responde en español.
- No inventes datos que no estén en el correo.
- Si algo no está claro, márcalo como faltante.
- request_type debe ser una de:
  desarrollo_web, automatizacion, ia, soporte, consultoria, otro
- estimated_complexity debe ser: baja, media o alta
- urgency debe ser: baja, media o alta
- needs_follow_up debe ser true si faltan detalles importantes
- detected_requirements debe contener requisitos concretos extraídos del correo
- requested_services debe contener servicios solicitados por el cliente
- summary y project_description deben ser claros y breves

EMAIL:
From: {email.from_email}
To: {email.to_email}
Subject: {email.subject}

Body:
{email.body}
"""
    return analysis_llm.invoke(prompt)


# 6) PASO 2: GENERAR EL PSEUDOPRESUPUESTO


def generate_budget_from_analysis(
    email: EmailInput, analysis: BudgetRequestAnalysis
) -> BudgetOutput:
    prompt = f"""
Eres un asistente comercial que genera pseudopresupuestos iniciales.

Tu tarea es devolver ÚNICAMENTE la estructura solicitada con un
presupuesto simple y razonable en EUR, basado en el análisis del correo.

Instrucciones:
- Es un PRESUPUESTO BORRADOR, no definitivo.
- No inventes requisitos avanzados no mencionados.
- Usa importes simples y coherentes con la complejidad.
- Debe incluir líneas de presupuesto claras.
- project_title debe ser breve.
- project_summary debe estar en español.
- scope_items debe resumir lo incluido.
- assumptions debe dejar claro qué se está suponiendo.
- exclusions debe dejar claro qué NO está incluido.
- timeline_estimate debe ser una estimación simple.
- tax_percent será 21.
- Calcula correctamente subtotal_eur, tax_amount_eur y total_eur.
- status debe ser "borrador" o "pendiente_revision" si faltan datos.

Guía orientativa de precios simples:
- consultoría inicial: 80 a 150 EUR
- automatización simple: 250 a 900 EUR
- desarrollo web simple: 500 a 1500 EUR
- integración IA simple: 400 a 1200 EUR
- soporte o ajustes menores: 100 a 300 EUR

EMAIL ORIGINAL:
From: {email.from_email}
To: {email.to_email}
Subject: {email.subject}

Body:
{email.body}

ANÁLISIS ESTRUCTURADO:
{analysis.model_dump_json(indent=2)}
"""
    return budget_llm.invoke(prompt)


# 7) FUNCIÓN PRINCIPAL DEL "AGENTE"


def process_budget_request(email: EmailInput) -> dict:
    analysis = analyze_email_for_budget(email)
    budget = generate_budget_from_analysis(email, analysis)

    return {
        "email_input": email.model_dump(),
        "analysis": analysis.model_dump(),
        "budget": budget.model_dump(),
    }


# 8) EJEMPLO DE USO

if __name__ == "__main__":
    fake_email = EmailInput(
        from_email="cliente@empresa.com",
        to_email="presupuestos@tuempresa.com",
        subject="Solicitud de presupuesto para automatizar respuestas",
        body=(
            "Hola, soy Marta de BlueNova. "
            "Necesitamos automatizar la clasificación de emails de clientes "
            "y generar respuestas iniciales para consultas frecuentes. "
            "Nos gustaría algo sencillo para empezar y tener una primera propuesta económica. "
            "La idea es tenerlo cuanto antes, idealmente este mes."
        ),
    )

    result = process_budget_request(fake_email)

    print("\n=== EMAIL DE ENTRADA ===")
    print(result["email_input"])

    print("\n=== ANALISIS ESTRUCTURADO ===")
    print(result["analysis"])

    print("\n=== PSEUDOPRESUPUESTO ===")
    print(result["budget"])
