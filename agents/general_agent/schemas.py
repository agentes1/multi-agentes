from pydantic import BaseModel


class GeneralResponseSchema(BaseModel):
    reply_text: str
