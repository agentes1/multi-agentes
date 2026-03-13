# 1. Importación de librerías necesarias
import json
from typing import Literal

from langchain.agents import AgentState, create_agent
from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
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


# 4. Definición del registro persistente de correo analizado
class StoredEmail(BaseModel):
    email_id: int
    from_email: str
    to_email: str
    subject: str
    body: str
    analysis: EmailSummary


# 5. Definición del estado personalizado del agente
class CustomAgentState(AgentState):
    analyzed_emails: list[dict] = Field(default_factory=list)
    last_email_summary: dict | None = None


# 6. Creación del modelo LLM usando Ollama local
llm = ChatOllama(
    model="qwen2.5:3b",
    base_url="http://localhost:11434",
    temperature=0,
)


# 7. Creación de una versión del modelo que devuelva salida estructurada
structured_llm = llm.with_structured_output(EmailSummary)


# 8. Definición de la herramienta que analiza y guarda emails en memoria
@tool
def analizar_email(
    email: EmailInput,
    runtime: ToolRuntime[None, CustomAgentState],
) -> Command:
    """
    Analiza un email y guarda su resultado en la memoria corta del agente.
    """

    # 8.1 Crear el prompt para el modelo
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
From: {email.from_email}
To: {email.to_email}
Subject: {email.subject}

Body:
{email.body}
"""

    # 8.2 Invocar el modelo con salida estructurada
    result = structured_llm.invoke(prompt)
    result_dict = result.model_dump()

    # 8.3 Recuperar el listado actual de correos guardados
    current_emails = runtime.state.get("analyzed_emails", [])

    # 8.4 Construir el nuevo registro persistente
    new_email_id = len(current_emails) + 1
    stored_email = StoredEmail(
        email_id=new_email_id,
        from_email=email.from_email,
        to_email=email.to_email,
        subject=email.subject,
        body=email.body,
        analysis=result,
    ).model_dump()

    # 8.5 Actualizar la memoria del agente
    return Command(
        update={
            "analyzed_emails": current_emails + [stored_email],
            "last_email_summary": result_dict,
            "messages": [
                ToolMessage(
                    content=(
                        f"Correo guardado en memoria con email_id={new_email_id}. "
                        f"Categoría: {result_dict['category']}. "
                        f"Urgencia: {result_dict['urgency']}. "
                        f"Requiere acción: {result_dict['action_required']}."
                    ),
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
    )


# 9. Definición de la herramienta para consultar memoria de correos
@tool
def consultar_memoria_correos(
    consulta: str,
    runtime: ToolRuntime[None, CustomAgentState],
) -> str:
    """
    Consulta la memoria de correos ya analizados usando lenguaje natural.
    """

    # 9.1 Leer memoria estructurada del estado
    analyzed_emails = runtime.state.get("analyzed_emails", [])

    # 9.2 Validar si hay correos guardados
    if not analyzed_emails:
        return "No hay correos analizados todavía."

    # 9.3 Crear contexto de memoria para consulta
    memory_context = json.dumps(analyzed_emails, ensure_ascii=False, indent=2)

    # 9.4 Crear prompt de consulta sobre la memoria
    prompt = f"""
Eres un asistente que consulta correos ya analizados.

Tienes una memoria estructurada con los correos previos y su análisis.
Debes responder usando solo la información disponible en esa memoria.
Si la memoria no contiene la respuesta, dilo claramente.
Resume en español y de forma precisa.

CONSULTA:
{consulta}

MEMORIA:
{memory_context}
"""

    # 9.5 Invocar el modelo para consultar la memoria
    response = llm.invoke(prompt)

    # 9.6 Devolver la respuesta final
    return response.content


# 10. Creación de memoria corta en RAM
checkpointer = InMemorySaver()


# 11. Creación del agente con estado personalizado
agent = create_agent(
    model=llm,
    tools=[analizar_email, consultar_memoria_correos],
    state_schema=CustomAgentState,
    system_prompt=(
        "Eres un asistente que analiza correos y consulta memoria. "
        "Cuando el usuario te pase un email, usa la tool analizar_email. "
        "Cuando el usuario pregunte por correos anteriores o información pasada, "
        "usa la tool consultar_memoria_correos. "
        "No inventes información."
    ),
    checkpointer=checkpointer,
)


# 12. Función auxiliar para imprimir mensajes del agente
def print_messages(response: dict) -> None:
    # 12.1 Recorrer y mostrar mensajes
    for msg in response["messages"]:
        print(type(msg).__name__, getattr(msg, "content", msg))


# 13. Función auxiliar para inspeccionar el estado persistido
def print_state(thread_id: str) -> None:

    # 13.1 Leer el snapshot del estado guardado para el thread
    snapshot = agent.get_state({"configurable": {"thread_id": thread_id}})
    state = snapshot.values

    # 13.2 Preparar una estructura limpia para imprimir
    cleaned_state = {
        "num_messages": len(state.get("messages", [])),
        "last_email_summary": state.get("last_email_summary"),
        "analyzed_emails_count": len(state.get("analyzed_emails", [])),
        "analyzed_emails": [],
    }

    # 13.3 Simplificar la lista de correos analizados
    for email in state.get("analyzed_emails", []):
        cleaned_state["analyzed_emails"].append(
            {
                "email_id": email.get("email_id"),
                "subject": email.get("subject"),
                "category": email.get("analysis", {}).get("category"),
                "urgency": email.get("analysis", {}).get("urgency"),
                "action_required": email.get("analysis", {}).get("action_required"),
            }
        )

    # 13.4 Mostrar el estado limpio
    print("\nESTADO PERSISTIDO\n")
    print(json.dumps(cleaned_state, ensure_ascii=False, indent=2))


# 14. Bloque principal de ejecución
if __name__ == "__main__":
    # 14.1 Definir thread_id fijo para que la memoria persista entre llamadas
    thread_id = "thread-demo"

    # 14.2 Crear correos de prueba
    fake_email_1 = {
        "from_email": "cliente@empresa.com",
        "to_email": "soporte@empresa.com",
        "subject": "Factura 1234 incorrecta",
        "body": "Hola, la factura 1234 tiene un importe incorrecto. Necesito corrección antes del viernes.",
    }

    fake_email_2 = {
        "from_email": "rrhh@empresa.com",
        "to_email": "empleado@empresa.com",
        "subject": "Entrevista final",
        "body": "Te confirmamos la entrevista final el jueves a las 10:00. Por favor confirma tu asistencia.",
    }

    # 14.3 Analizar primer correo
    response_1 = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Analiza este email:\n"
                    + json.dumps(fake_email_1, ensure_ascii=False),
                }
            ]
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    print("\nPRIMERA INTERACCIÓN\n")
    print_messages(response_1)
    print_state(thread_id)

    # 14.4 Analizar segundo correo
    response_2 = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Analiza este email:\n"
                    + json.dumps(fake_email_2, ensure_ascii=False),
                }
            ]
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    print("\nSEGUNDA INTERACCIÓN\n")
    print_messages(response_2)
    print_state(thread_id)

    # 14.5 Consultar memoria de correos pasados
    response_3 = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "¿Qué información importante recuerdas de los correos pasados?",
                }
            ]
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    print("\nTERCERA INTERACCIÓN\n")
    print_messages(response_3)
    print_state(thread_id)
