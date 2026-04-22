# api.py
# servidor HTTP: expone el pipeline como endpoint REST
# cada canal de entrada (email, chat, webhook) llama a POST /process
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from polling import TicketPollingService
from pipeline import run_pipeline
from webhooks import build_ticket_webhook_orchestrator

app = FastAPI(title="Multi-agente presupuestos")

# permite llamadas desde herramientas externas y scripts locales
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# esquema de entrada: acepta cualquier canal (email, chat, etc)
class ProcessRequest(BaseModel):
    source_input: dict
    thread_id: str | None = None  # opcional: para rastrear sesiones concretas


# esquema de respuesta para documentación automática en /docs
class ProcessResponse(BaseModel):
    ok: bool
    thread_id: str | None = None
    stage: str | None = None  # qué agente falló (solo si ok=False)
    error: str | None = None  # mensaje de error (solo si ok=False)
    validation_notes: list[str] = []  # avisos no bloqueantes del intake
    normalized_request: dict = {}
    quote_result: dict = {}
    final_text: str = ""


class TicketWebhookRequest(BaseModel):
    ticket_id: int
    thread_id: str | None = None


class TicketWebhookResponse(BaseModel):
    ok: bool
    stage: str | None = None
    error: str | None = None
    route_name: str | None = None
    agent_name: str | None = None
    ticket: dict = {}
    normalized_request: dict = {}
    assistant_reply: str = ""
    quote_summary: dict = {}
    chat_channel: dict = {}
    chat_message_id: int | None = None
    trace: list[str] = []


class TicketPollingRequest(BaseModel):
    limit: int = 50
    thread_prefix: str = "ticket-poll"


class TicketPollingResponse(BaseModel):
    seen_ticket_ids: list[int] = []
    new_ticket_ids: list[int] = []
    processed_count: int
    results: list[dict] = []


@app.post("/process", response_model=ProcessResponse)
async def process(request: ProcessRequest):
    result = await run_pipeline(
        source_input=request.source_input,
        thread_id=request.thread_id,
    )
    # usamos 400 para errores de negocio y reservamos 422 para errores de validación Pydantic
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@app.post("/webhooks/odoo/tickets", response_model=TicketWebhookResponse)
async def odoo_ticket_webhook(request: TicketWebhookRequest):
    result = await build_ticket_webhook_orchestrator().handle_ticket_created(
        ticket_id=request.ticket_id,
        thread_id=request.thread_id,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@app.post("/polling/odoo/tickets", response_model=TicketPollingResponse)
async def poll_odoo_tickets(request: TicketPollingRequest):
    service = TicketPollingService()
    return await service.poll_new_tickets(
        limit=request.limit,
        thread_prefix=request.thread_prefix,
    )


# endpoint de salud para comprobar que el servidor está vivo
@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
