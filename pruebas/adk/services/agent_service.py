###
# En los servicios definimos algunas funciones que nos ayudan a gestionar al agente
# Este servicio nos ayuda a llamarlo una vez nos ha llegado una petición, que en esta prueba es con un mail que forzamos desde un JSON
# El servicio recive un mail, y levanta el agente para que responda
###
import asyncio

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from adk.agente_adk.agent import root_agent

async def run_agent_async(email):
    prompt = f"""
You received the following email:

Subject:
{email['subject']}

Content:
{email['body']}

Generate a professional response offering ERP information or a quote.
"""
    #Esto almacena las conversaciones, en este modo es solo de prueba y se guarda en memoria gracias a una función de ADK
    session_service = InMemorySessionService() 

    runner = Runner(
        app_name="quote_agent",
        agent=root_agent,
        session_service=session_service
    )
    session = await session_service.create_session(
        app_name="quote_agent",
        user_id="test_user"
    )
    message = Content(
        role="user",
        parts=[Part(text=prompt)]
    )
    response_text = ""

    async for event in runner.run_async(
        session_id=session.id,
        user_id="test_user",
        new_message=message
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    response_text += part.text

    return response_text

def run_agent(email):
    return asyncio.run(run_agent_async(email))