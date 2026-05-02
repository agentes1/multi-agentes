"""API HTTP principal del proyecto."""

import json
import traceback
import uuid
from datetime import datetime

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from agents.budget_agent.dependencies import build_dependencies as build_budget_deps
from agents.budget_agent.graph import build_budget_graph
from agents.intake_agent.dependencies import build_dependencies as build_intake_deps
from agents.intake_agent.graph import build_intake_graph
from orchestration.assistant_discuss import build_discuss_message_orchestrator
from orchestration.assistant_email import build_incoming_email_orchestrator
from orchestration.assistant_entry import build_ticket_entry_orchestrator

app = FastAPI(title="Multi-agente presupuestos")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Schemas ──────────────────────────────────────────────────────────────────

class AssistantTicketEntryRequest(BaseModel):
    ticket_id: int | None = None
    title: str = ""
    description: str = ""
    partner_name: str = ""
    partner_email: str = ""
    thread_id: str | None = None


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


class AssistantIncomingEmailRequest(BaseModel):
    inbox_id: int | None = None
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


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/assistant/ticket-entry")
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
        return JSONResponse(content=result)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "trace": traceback.format_exc()}
        )


@app.post("/assistant/discuss-message")
async def assistant_discuss_message(request: AssistantDiscussMessageRequest):
    try:
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
        return JSONResponse(content=result)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@app.post("/assistant/incoming-email")
async def assistant_incoming_email(request: AssistantIncomingEmailRequest):
    try:
        payload = {
            "inbox_id": request.inbox_id,
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
        return JSONResponse(content=result)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


# ─── Frontend estático ────────────────────────────────────────────────────────

@app.get("/")
async def frontend():
    return FileResponse("frontend.html")


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)