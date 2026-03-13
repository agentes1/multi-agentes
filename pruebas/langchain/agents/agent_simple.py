from typing import Literal

from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field


# 1) Entrada simulada tipo email
class EmailInput(BaseModel):
    from_email: str
    to_email: str
    subject: str
    body: str


# 2) Estructura de salida que quieres obtener
class EmailSummary(BaseModel):
    language: str = Field(description="Idioma detectado, por ejemplo es o en")
    category: Literal["ventas", "soporte", "facturacion", "spam", "otro"]
    urgency: Literal["baja", "media", "alta"]
    summary: str = Field(description="Resumen breve y claro del correo")
    action_required: bool
    requested_actions: list[str] = Field(default_factory=list)


# 3) Modelo local de Ollama
llm = ChatOllama(
    model="qwen2.5:3b",
    base_url="http://localhost:11434",
    temperature=0,
)

# 4) Le pedimos salida estructurada
structured_llm = llm.with_structured_output(EmailSummary)


def process_email(email: EmailInput) -> EmailSummary:
    prompt = f"""
Eres un asistente experto en analizar correos.

Tu tarea es leer el siguiente email y devolver únicamente la estructura solicitada.

Reglas:
- Resume en español.
- No inventes datos.
- category debe ser una de estas: ventas, soporte, facturacion, spam, otro
- urgency debe ser baja, media o alta
- action_required debe ser true si el correo requiere hacer algo
- requested_actions debe listar acciones concretas si existen

EMAIL:
From: {email.from_email}
To: {email.to_email}
Subject: {email.subject}

Body:
{email.body}
"""
    return structured_llm.invoke(prompt)


if __name__ == "__main__":
    fake_email = EmailInput(
        from_email="cliente@empresa.com",
        to_email="soporte@empresa.com",
        subject="Factura 1234 incorrecta",
        body="Hola, la factura 1234 tiene un importe incorrecto. Necesito corrección antes del viernes. Gracias.",
    )

    result = process_email(fake_email)

    print("\n=== EMAIL DE ENTRADA ===")
    print(fake_email.model_dump())

    print("\n=== RESUMEN ESTRUCTURADO ===")
    print(result.model_dump())
