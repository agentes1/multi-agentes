# api.py
# servidor HTTP: expone el pipeline como endpoint REST
# cada canal de entrada (email, chat, webhook) llama a POST /process
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipeline import run_pipeline

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


# endpoint de salud para comprobar que el servidor está vivo
@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
