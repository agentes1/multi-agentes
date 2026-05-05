from typing import Literal
from pydantic import BaseModel, Field

class IntakeRequestSchema(BaseModel):
    """Solicitud entendida desde el correo."""
    company_name: str = ""
    project_summary: str
    requirements: list[str] = Field(default_factory=list)
    urgency: str = "media"
    ticket_type: Literal["budget", "issue", "discard"] = "discard"
    missing_information: list[str] = Field(default_factory=list)

class HelpdeskTicketSchema(BaseModel):
    """Datos validados para crear el ticket."""
    title: str
    description: str
    priority: Literal["0", "1", "2"] = "1"
    team_name: str
    type_name: str
    category_name: str
    tag_names: list[str] = Field(default_factory=list)
    motive_name: str | None = None
    company_id: int | None = None
    company_name: str | None = None
    detected_company_name: str = ""
    partner_name: str = ""
    partner_email: str = ""