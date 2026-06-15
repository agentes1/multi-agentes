"""API HTTP principal del proyecto.

Este archivo expone los puntos de entrada externos del sistema:
- ticket creado manualmente en Odoo
- mensaje nuevo en Discuss
- correo entrante procesado por mail_inbox_input
- presupuesto creado al marcar un ticket como Ready for next stage
- consulta RAG sobre tickets resueltos

Cada endpoint delega la lógica real en un orquestador de orchestration/,
de modo que la API se mantenga como una capa fina de entrada/salida.
"""

import traceback

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from orchestration.assistant_discuss import build_discuss_message_orchestrator
from orchestration.assistant_budget import build_budget_from_ticket_orchestrator
from orchestration.assistant_email import build_incoming_email_orchestrator
from orchestration.assistant_entry import build_ticket_entry_orchestrator
from orchestration.assistant_sales import build_sales_from_ticket_orchestrator

app = FastAPI(title="Multi-agente presupuestos")

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
    normalized_request: dict = Field(default_factory=dict)
    quote_summary: dict = Field(default_factory=dict)
    error: str | None = None
    trace: list[str] = Field(default_factory=list)


class AssistantDiscussMessageRequest(BaseModel):
    ticket_id: int | None = None
    ticket_title: str = ""
    ticket_description: str = ""
    ticket_partner_name: str = ""
    ticket_partner_email: str = ""
    ticket_team: str = ""
    ticket_category: str = ""
    ticket_type: str = ""
    ticket_stage: str = ""
    assistant_route_name: str = ""
    channel_id: int | None = None
    channel_name: str = ""
    message_id: int | None = None
    author_name: str = ""
    author_email: str = ""
    body: str = ""
    recent_messages: list[dict] = Field(default_factory=list)
    thread_id: str | None = None


class AssistantDiscussMessageResponse(BaseModel):
    ok: bool
    route_name: str | None = None
    agent_name: str | None = None
    reply_text: str = ""
    normalized_request: dict = Field(default_factory=dict)
    quote_summary: dict = Field(default_factory=dict)
    actions: list[dict] = Field(default_factory=list)
    error: str | None = None
    trace: list[str] = Field(default_factory=list)


class AssistantIncomingEmailRequest(BaseModel):
    inbox_id: int | None = None
    notify_partner_id: int | None = None
    subject: str = ""
    email_from: str = ""
    email_to: str = ""
    email_cc: str = ""
    body_html: str = ""
    body: str = ""
    message_id: str = ""
    sender_name: str = ""
    received_date: str = ""
    thread_id: str | None = None


class AssistantIncomingEmailResponse(BaseModel):
    ok: bool
    ticket_id: int | None = None
    final_text: str = ""
    reply_text: str = ""
    route_name: str | None = None
    agent_name: str | None = None
    normalized_request: dict = Field(default_factory=dict)
    ticket_payload: dict = Field(default_factory=dict)
    quote_summary: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    trace: list[str] = Field(default_factory=list)


class AssistantBudgetFromTicketRequest(BaseModel):
    ticket_id: int | None = None
    notify_partner_id: int | None = None
    title: str = ""
    description: str = ""
    partner_id: int | None = None
    partner_name: str = ""
    partner_email: str = ""
    thread_id: str | None = None


class AssistantBudgetFromTicketResponse(BaseModel):
    ok: bool
    agent_name: str | None = None
    reply_text: str = ""
    sale_order_id: int | None = None
    normalized_request: dict = Field(default_factory=dict)
    quote_summary: dict = Field(default_factory=dict)
    error: str | None = None
    trace: list[str] = Field(default_factory=list)


class AssistantSalesFromTicketRequest(BaseModel):
    ticket_id: int | None = None
    title: str = ""
    description: str = ""
    partner_id: int | None = None
    partner_name: str = ""
    partner_email: str = ""
    thread_id: str | None = None


class AssistantSalesFromTicketResponse(BaseModel):
    ok: bool
    agent_name: str | None = None
    reply_text: str = ""
    crm_lead_id: int | None = None
    crm_summary: dict = Field(default_factory=dict)
    error: str | None = None
    trace: list[str] = Field(default_factory=list)


class AssistantRAGRequest(BaseModel):
    input_text: str = ""
    thread_id: str | None = None


class AssistantRAGResponse(BaseModel):
    ok: bool
    reply_text: str = ""
    retrieved_tickets: list[dict] = Field(default_factory=list)
    error: str | None = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/assistant/ticket-entry", response_model=AssistantTicketEntryResponse)
async def assistant_ticket_entry(request: AssistantTicketEntryRequest):
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.post("/assistant/discuss-message", response_model=AssistantDiscussMessageResponse)
async def assistant_discuss_message(request: AssistantDiscussMessageRequest):
    try:
        payload = {
            "ticket_id": request.ticket_id,
            "ticket_title": request.ticket_title,
            "ticket_description": request.ticket_description,
            "ticket_partner_name": request.ticket_partner_name,
            "ticket_partner_email": request.ticket_partner_email,
            "ticket_team": request.ticket_team,
            "ticket_category": request.ticket_category,
            "ticket_type": request.ticket_type,
            "ticket_stage": request.ticket_stage,
            "assistant_route_name": request.assistant_route_name,
            "channel_id": request.channel_id,
            "channel_name": request.channel_name,
            "message_id": request.message_id,
            "author_name": request.author_name,
            "author_email": request.author_email,
            "body": request.body,
            "recent_messages": request.recent_messages,
        }
        result = await build_discuss_message_orchestrator().handle_discuss_message(
            payload=payload,
            thread_id=request.thread_id,
        )
        if not result["ok"]:
            raise HTTPException(status_code=400, detail=result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.post("/assistant/incoming-email", response_model=AssistantIncomingEmailResponse)
async def assistant_incoming_email(request: AssistantIncomingEmailRequest):
    try:
        payload = {
            "inbox_id": request.inbox_id,
            "notify_partner_id": request.notify_partner_id,
            "subject": request.subject,
            "email_from": request.email_from,
            "email_to": request.email_to,
            "email_cc": request.email_cc,
            "body_html": request.body_html,
            "body": request.body,
            "message_id": request.message_id,
            "sender_name": request.sender_name,
            "received_date": request.received_date,
        }
        result = await build_incoming_email_orchestrator().handle_incoming_email(
            payload=payload,
            thread_id=request.thread_id,
        )
        if not result["ok"]:
            raise HTTPException(status_code=400, detail=result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.post("/assistant/budget-from-ticket", response_model=AssistantBudgetFromTicketResponse)
async def assistant_budget_from_ticket(request: AssistantBudgetFromTicketRequest):
    try:
        ticket = {
            "id": request.ticket_id,
            "notify_partner_id": request.notify_partner_id,
            "name": request.title,
            "description": request.description,
            "partner_id": request.partner_id,
            "partner_name": request.partner_name,
            "partner_email": request.partner_email,
        }
        result = await build_budget_from_ticket_orchestrator().handle_budget_from_ticket(
            ticket=ticket,
            thread_id=request.thread_id or f"odoo-ticket-budget-{request.ticket_id}",
        )
        if not result["ok"]:
            raise HTTPException(status_code=400, detail=result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.post("/assistant/sales-from-ticket", response_model=AssistantSalesFromTicketResponse)
async def assistant_sales_from_ticket(request: AssistantSalesFromTicketRequest):
    try:
        ticket = {
            "id": request.ticket_id,
            "name": request.title,
            "description": request.description,
            "partner_id": request.partner_id,
            "partner_name": request.partner_name,
            "partner_email": request.partner_email,
        }
        result = await build_sales_from_ticket_orchestrator().handle_sales_from_ticket(
            ticket=ticket,
            thread_id=request.thread_id or f"odoo-ticket-sales-{request.ticket_id}",
        )
        if not result["ok"]:
            raise HTTPException(status_code=400, detail=result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.post("/assistant/rag", response_model=AssistantRAGResponse)
async def assistant_rag(request: AssistantRAGRequest):
    try:
        from agents.rag_agent.graph import build_rag_graph
        from agents.rag_agent.dependencies import build_dependencies

        deps = build_dependencies()
        graph = build_rag_graph()
        result = await graph.ainvoke(
            {"input_text": request.input_text},
            config={"configurable": {"deps": deps}},
        )
        return {
            "ok": True,
            "reply_text": result.get("reply_text", ""),
            "retrieved_tickets": result.get("retrieved_tickets", []),
        }
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ─── Frontend estático ────────────────────────────────────────────────────────

@app.get("/")
async def frontend():
    return FileResponse("frontend.html")


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)