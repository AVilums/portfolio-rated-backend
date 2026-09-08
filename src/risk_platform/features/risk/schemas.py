from decimal import Decimal

from pydantic import BaseModel, Field


class VaRRequest(BaseModel):
    losses: list[Decimal] = Field(min_length=1)
    confidence: Decimal = Field(default=Decimal("0.99"), gt=0, lt=1)


class VaRResponse(BaseModel):
    metric: str = "historical_var"
    value: Decimal
    confidence: Decimal
    observation_count: int
