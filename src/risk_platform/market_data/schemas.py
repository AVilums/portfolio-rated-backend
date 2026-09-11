from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Percentage = Annotated[Decimal, Field(ge=0, le=100, allow_inf_nan=False)]
Code = Annotated[str, Field(min_length=1, max_length=40, pattern=r"^[A-Z0-9][A-Z0-9.:-]*$")]


class DataModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Holding(DataModel):
    # Provider-stable identifier, such as ISIN; ticker alone is not globally unique.
    identifier: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=300)
    weight: Percentage
    sector: str | None = Field(default=None, min_length=1, max_length=100)
    country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")


class Quote(DataModel):
    price: Decimal = Field(gt=0, allow_inf_nan=False)
    as_of: AwareDatetime


class EtfSnapshot(DataModel):
    schema_version: Literal[1] = 1
    instrument_type: Literal["ETF"] = "ETF"
    ticker: Code
    provider_symbol: Code | None = None
    exchange: Code
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    name: str = Field(min_length=1, max_length=300)
    source: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    as_of: AwareDatetime
    isin: str | None = Field(default=None, pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
    asset_class: str | None = Field(default=None, min_length=1, max_length=100)
    expense_ratio: Percentage | None = None
    quote: Quote | None = None
    holdings: list[Holding] | None = Field(default=None, max_length=20000)
    holdings_as_of: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_components(self) -> Self:
        if self.quote is not None and self.quote.as_of > self.as_of:
            raise ValueError("Quote timestamp cannot be later than snapshot timestamp.")
        if (self.holdings is None) != (self.holdings_as_of is None):
            raise ValueError("Holdings and their timestamp must be supplied together.")
        if self.holdings_as_of is not None and self.holdings_as_of > self.as_of:
            raise ValueError("Holdings timestamp cannot be later than snapshot timestamp.")
        if self.holdings is not None:
            if len({h.identifier for h in self.holdings}) != len(self.holdings):
                raise ValueError("Holding identifiers must be unique.")
            if sum((h.weight for h in self.holdings), Decimal(0)) > 100:
                raise ValueError("Reported holdings weights must not exceed 100%.")
        return self


class StoredSnapshot(DataModel):
    id: UUID
    ingested_at: datetime
    data: EtfSnapshot
    holdings_coverage: Percentage | None
