from pydantic import BaseModel


class RAGResponseSchema(BaseModel):
    """Respuesta validada del agente RAG."""
    reply_text: str
    sources: list[str] = []