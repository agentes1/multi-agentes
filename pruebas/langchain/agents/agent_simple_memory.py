# No pilla contexto? Culpa del modelo?
# 1. Importación de librerías necesarias
import json
from typing import Literal

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel, Field


# 2. Definición del esquema de entrada del email
class EmailInput(BaseModel):
    from_email: str
    to_email: str
    subject: str
    body: str


# 3. Definición del esquema de salida estructurada
class EmailSummary(BaseModel):
    language: str = Field(description="Idioma detectado")
    category: Literal["ventas", "soporte", "facturacion", "spam", "otro"]
    urgency: Literal["baja", "media", "alta"]
    summary: str = Field(description="Resumen breve del correo")
    action_required: bool
    requested_actions: list[str] = Field(default_factory=list)


# 4. Creación del modelo LLM usando Ollama local
llm = ChatOllama(
    model="llama3.2:3b",
    base_url="http://localhost:11434",
    temperature=0,
)


# 5. Creación de una versión del modelo que devuelva salida estructurada
structured_llm = llm.with_structured_output(EmailSummary)


# 6. Definición de la herramienta que analizará emails
@tool
def analizar_email(
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
) -> dict:
    """
    Analiza un email en formato JSON y devuelve un resumen estructurado.
    """

    # 6.2 Crear el prompt que se enviará al modelo
    prompt = f"""
Eres un analista experto en correos empresariales.

Lee el email y devuelve únicamente la estructura pedida.

Reglas:
- Resume en español.
- No inventes datos.
- category debe ser una de estas: ventas, soporte, facturacion, spam, otro
- urgency debe ser una de estas: baja, media, alta
- action_required debe ser true si el correo requiere actuar
- requested_actions debe listar acciones concretas si existen

EMAIL:
From: {from_email}
To: {to_email}
Subject: {subject}

Body:
{body}
"""

    # 6.3 Invocar el modelo con salida estructurada
    result = structured_llm.invoke(prompt)

    # 6.4 Convertir el resultado a diccionario
    return result.model_dump()


# 7. Creación de memoria corta en RAM
checkpointer = InMemorySaver()


# 8. Creación del agente con la herramienta y memoria
agent = create_agent(
    model=llm,
    tools=[analizar_email],
    system_prompt=(
        "Eres un asistente que analiza correos. "
        "Si el usuario proporciona un email nuevo, usa la tool analizar_email. "
        "Si el usuario hace una pregunta sobre un correo ya analizado, responde usando el historial de la conversación "
        "sin volver a llamar a la tool, salvo que falten datos."
    ),
    checkpointer=checkpointer,
)


# 9. Bloque principal de ejecución
if __name__ == "__main__":
    # 9.1 Crear un email de prueba
    fake_email = {
        "from_email": "cliente@empresa.com",
        "to_email": "soporte@empresa.com",
        "subject": "Factura 1234 incorrecta",
        "body": "Hola, la factura 1234 tiene un importe incorrecto. Necesito corrección antes del viernes.",
    }

    # 9.2 Primera interacción con el agente
    response_1 = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Analiza este email:\n" + json.dumps(fake_email, ensure_ascii=False)
                    ),
                }
            ]
        },
        config={"configurable": {"thread_id": "thread-demo"}},
    )

    # 9.3 Mostrar mensajes generados en la primera interacción
    for msg in response_1["messages"]:
        print(type(msg).__name__, getattr(msg, "content", msg))

    # 9.4 Segunda interacción para comprobar memoria
    response_2 = agent.invoke(
        {"messages": [{"role": "user", "content": "¿Qué categoría tenía el último correo?"}]},
        config={"configurable": {"thread_id": "thread-demo"}},
    )

    # 9.5 Mostrar mensajes generados en la segunda interacción
    for msg in response_2["messages"]:
        print(type(msg).__name__, getattr(msg, "content", msg))
