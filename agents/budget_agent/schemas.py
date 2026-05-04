from pydantic import BaseModel, Field


class BudgetCreateSchema(BaseModel):
    partner_id: int
    company_name: str
    selected_products: list[dict] = Field(default_factory=list)