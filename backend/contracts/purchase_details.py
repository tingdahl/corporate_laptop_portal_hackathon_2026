from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ParsedTransactionResponse(ContractModel):
    email: str
    amount_signed: float
    currency: str
    date: date


class PurchaseSummaryResponse(ContractModel):
    purchase_date: date
    window_end_date: date
    next_refresh_date: date
    currency: str
    net_amount_local: float
    net_amount_usd: float | None = None
    exchange_rate_local_per_usd: float | None = None
    current_depreciated_value_local: float
    current_depreciated_value_usd: float | None = None
    anomalies: list[str] = Field(default_factory=list)
    transactions: list[ParsedTransactionResponse] = Field(default_factory=list)


class PurchaseDetailsResponse(ContractModel):
    employee_email: str
    purchases: list[PurchaseSummaryResponse]


class PurchaseEligibilityResponse(ContractModel):
    employee_email: str
    eligible_for_new_laptop: bool
    latest_purchase_date: date | None = None
    next_planned_laptop_refresh: date | None = None
    writeoff_months: int


class EmployeePurchaseRowResponse(ContractModel):
    employee_email: str
    latest_purchase_date: date


class EmployeesPurchaseListResponse(ContractModel):
    total_employees: int
    employees: list[EmployeePurchaseRowResponse]
