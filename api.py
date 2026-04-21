# api.py
# servidor HTTP: expone el pipeline de tickets como endpoint REST
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipeline import run_ticket_pipeline

app = FastAPI(title="Multi-agente tickets")

# permite llamadas desde herramientas externas y scripts locales
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# esquema de entrada: representa un correo listo para procesar
class ProcessRequest(BaseModel):
    email_subject: str
    email_body: str
    sender_email: str
    sender_name: str | None = None
    team_name: str | None = None


# esquema de respuesta: refleja el estado real del pipeline actual
class ProcessResponse(BaseModel):
    error: str | None = None
    normalized_ticket: dict = {}
    partner_id: int | None = None
    resolved_fields: dict = {}
    ticket_vals: dict = {}
    ticket_id: int | None = None


@app.post("/process", response_model=ProcessResponse)
async def process(request: ProcessRequest):
    result = await run_ticket_pipeline(
        email_subject=request.email_subject,
        email_body=request.email_body,
        sender_email=request.sender_email,
        sender_name=request.sender_name,
        team_name=request.team_name,
    )

    # usamos 400 para errores de negocio y reservamos 422 para errores de validación Pydantic
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result)
    return result


# endpoint de salud para comprobar que el servidor está vivo
@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
