from pydantic import BaseModel, ConfigDict, EmailStr, Field


class BudgetLine(BaseModel):
    model_config = ConfigDict(extra="ignore")

    product_name: str
    quantity: int = 1
    product_id: int | None = None
    odoo_product_name: str | None = None
    product_code: str | None = None


class Budget(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    company_name: str | None = None
    customer_email: EmailStr | None = None
    notes: str | None = None
    lines: list[BudgetLine] = Field(default_factory=list)

    partner_id: int | None = None
    sale_order_id: int | None = None
    subtotal: float = 0
    total: float = 0
    currency: str = "EUR"

    unmatched_products: list[str] = Field(default_factory=list)