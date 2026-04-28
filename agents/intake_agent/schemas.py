from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class IntakeRequestSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company_name: str = ""
    project_summary: str = ""
    requirements: list[str] = Field(default_factory=list)
    urgency: str = ""
    ticket_type: str = ""
    missing_information: list[str] = Field(default_factory=list)
