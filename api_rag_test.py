import traceback
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="RAG Agent Test")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AssistantRAGRequest(BaseModel):
    input_text: str = ""

class AssistantRAGResponse(BaseModel):
    ok: bool
    reply_text: str = ""
    retrieved_tickets: list[dict] = Field(default_factory=list)
    error: str | None = None

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

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("api_rag_test:app", host="0.0.0.0", port=8000, reload=False)