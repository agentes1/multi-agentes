import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from assistant_discuss import build_discuss_message_orchestrator
from assistant_entry import build_ticket_entry_orchestrator

app = FastAPI(title="Multi-agente presupuestos")

# permite llamadas desde herramientas externas y scripts locales
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AssistantTicketEntryRequest(BaseModel):
    ticket_id: int | None = None
    title: str = ""
    description: str = ""
    partner_name: str = ""
    partner_email: str = ""
    thread_id: str | None = None


class AssistantTicketEntryResponse(BaseModel):
    ok: bool
    route_name: str | None = None
    agent_name: str | None = None
    reply_text: str = ""
    normalized_request: dict = {}
    quote_summary: dict = {}
    error: str | None = None
    trace: list[str] = []


class AssistantDiscussMessageRequest(BaseModel):
    ticket_id: int | None = None
    ticket_title: str = ""
    channel_id: int | None = None
    channel_name: str = ""
    message_id: int | None = None
    author_name: str = ""
    author_email: str = ""
    body: str = ""
    thread_id: str | None = None


class AssistantDiscussMessageResponse(BaseModel):
    ok: bool
    route_name: str | None = None
    agent_name: str | None = None
    reply_text: str = ""
    normalized_request: dict = {}
    quote_summary: dict = {}
    error: str | None = None
    trace: list[str] = []


@app.post("/assistant/ticket-entry", response_model=AssistantTicketEntryResponse)
async def assistant_ticket_entry(request: AssistantTicketEntryRequest):
    ticket = {
        "id": request.ticket_id,
        "name": request.title,
        "description": request.description,
        "partner_name": request.partner_name,
        "partner_email": request.partner_email,
    }
    result = await build_ticket_entry_orchestrator().handle_ticket_entry(
        ticket=ticket,
        thread_id=request.thread_id,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@app.post("/assistant/discuss-message", response_model=AssistantDiscussMessageResponse)
async def assistant_discuss_message(request: AssistantDiscussMessageRequest):
    payload = {
        "ticket_id": request.ticket_id,
        "ticket_title": request.ticket_title,
        "channel_id": request.channel_id,
        "channel_name": request.channel_name,
        "message_id": request.message_id,
        "author_name": request.author_name,
        "author_email": request.author_email,
        "body": request.body,
    }
    result = await build_discuss_message_orchestrator().handle_discuss_message(
        payload=payload,
        thread_id=request.thread_id,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result)
    return result


# endpoint de salud para comprobar que el servidor está vivo
@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
