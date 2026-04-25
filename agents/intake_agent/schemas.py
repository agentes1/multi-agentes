from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Ticket(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Campos de texto (LLM)
    title: str
    description: str
    customer_email: EmailStr | None = None
    company_name: str | None = None
    partner_name: str | None = None
    ticket_type: str | None = None
    category: str | None = None
    team: str | None = None
    priority: str | None = None
    tags: list[str] = Field(default_factory=list)

    # Campos resueltos (IDs de Odoo)
    priority_odoo: Literal["0", "1", "2"] = "1"
    partner_id: int | None = None
    team_id: int | None = None
    type_id: int | None = None
    category_id: int | None = None
    tag_ids: list[int] = Field(default_factory=list)

    # Meta
    company_is_new: bool = False
    missing_fields: list[str] = Field(default_factory=list)