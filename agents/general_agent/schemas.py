from pydantic import BaseModel

class GeneralResponseSchema(BaseModel):
    """Respuesta validada del agente general."""
    reply_text: str