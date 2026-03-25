from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.common import UrgencyLevel


class NormalizedRequest(BaseModel):
    company_name: str = Field(default="Desconocido")
    project_summary: str = Field(default="")
    requirements: list[str] = Field(default_factory=list)
    urgency: UrgencyLevel = Field(default="media")
    missing_information: list[str] = Field(default_factory=list)


class QuoteLine(BaseModel):
    product_code: str
    description: str
    unit_price: float
    quantity: int = 1
    line_total: float


class QuoteResult(BaseModel):
    company_name: str
    lines: list[QuoteLine] = Field(default_factory=list)
    subtotal: float = 0.0
    discount: float = 0.0
    total: float = 0.0
    currency: str = "EUR"
    warnings: list[str] = Field(default_factory=list)
    version: int = 1
    based_on_previous_quote: bool = False


class RetrievedQuoteMemory(BaseModel):
    company_name: str
    last_quote_total: float | None = None
    last_quote_date: str | None = None
    last_product_codes: list[str] = Field(default_factory=list)
    quote_count: int = 0


class StoredQuoteMemory(BaseModel):
    company_name: str
    normalized_request: dict
    selected_products: list[str]
    quote_result: dict
    final_text: str
    timestamp: str
