from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Model-extracted laptop fields
# ---------------------------------------------------------------------------


class ExtractedLaptopFields(ContractModel):
    cpu_model: str | None = None
    cpu_cores: int | None = Field(default=None, ge=1)
    ram_gb: int | None = Field(default=None, ge=1)
    disk_gb: int | None = Field(default=None, ge=1)
    quoted_price: float | None = Field(
        default=None,
        description="Main price from the quote in local currency. Preferably: WITH warranty, WITHOUT taxes, WITHOUT shipping.",
    )
    includes_warranty: bool | None = Field(
        default=None,
        description="True if quoted_price includes warranty cost, False if not, null if unknown.",
    )
    includes_tax: bool | None = Field(
        default=None,
        description="True if quoted_price includes tax, False if not, null if unknown.",
    )
    includes_shipping: bool | None = Field(
        default=None,
        description="True if quoted_price includes shipping, False if not, null if unknown.",
    )
    warranty_cost: float | None = Field(
        default=None,
        description="Separate warranty cost when itemized, in local currency.",
    )
    tax_amount: float | None = Field(
        default=None,
        description="Separate tax amount when itemized, in local currency.",
    )
    shipping_cost: float | None = Field(
        default=None,
        description="Separate shipping cost when itemized, in local currency.",
    )
    warranty_years: float | None = Field(default=None, ge=0)
    currency: str = Field(description="Detected currency code, e.g. 'USD', 'SEK'.")


# ---------------------------------------------------------------------------
# Exchange rate
# ---------------------------------------------------------------------------


class ExchangeRateInfo(ContractModel):
    currency: str = Field(description="Local currency code.")
    rate_local_per_usd: float = Field(
        description="Number of local currency units per 1 USD (exchange rate captured at interpretation time)."
    )
    captured_at_utc: datetime


# ---------------------------------------------------------------------------
# Pricing calculator
# ---------------------------------------------------------------------------


class PricingCalculatorResult(ContractModel):
    laptop_price_incl_warranty_usd: float | None = None
    taxes_usd: float | None = None
    shipping_usd: float | None = None
    laptop_base_reimbursed_usd: float | None = None
    tax_reimbursed_usd: float | None = None
    canonical_reimbursed_usd: float | None = None
    total_purchase_usd: float | None = None
    employee_own_expense_usd: float | None = None
    has_missing_inputs: bool = Field(
        default=False,
        description="True when one or more required inputs were missing or unparseable.",
    )


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------


class ComplianceResult(ContractModel):
    cpu_pass: bool | None = None
    disk_pass: bool | None = None
    ram_pass: bool | None = None
    price_pass: bool | None = None
    warranty_pass: bool | None = Field(
        default=None,
        description="Warranty must be at least 3 years.",
    )


class QuoteOverrides(ContractModel):
    currency_override: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=4,
        description="Manual override for detected currency code (max 4 chars).",
    )
    price_override_local: Optional[str] = Field(
        default=None,
        pattern=r"^\d{1,10}$",
        description="Manual override for local-currency laptop amount as digits-only string (1-10 digits).",
    )
    includes_tax: Optional[bool] = Field(
        default=None,
        description="Tri-state override for whether the supplied amount includes tax: null=auto, true=yes, false=no.",
    )
    includes_shipping: Optional[bool] = Field(
        default=None,
        description="Tri-state override for whether the supplied amount includes shipping: null=auto, true=yes, false=no.",
    )
    includes_warranty: Optional[bool] = Field(
        default=None,
        description="Tri-state override for whether the supplied amount includes warranty: null=auto, true=yes, false=no.",
    )


# ---------------------------------------------------------------------------
# Interpret endpoint  POST /api/new_laptop
# ---------------------------------------------------------------------------


class InterpretQuoteResponse(ContractModel):
    interpretation_id: str = Field(
        description="Opaque identifier used in the subsequent accept call."
    )
    fields: ExtractedLaptopFields
    exchange_rate: ExchangeRateInfo
    pricing: PricingCalculatorResult
    compliance: ComplianceResult
    processed_image_url: str | None = Field(
        default=None,
        description="URL to retrieve the blurred image preview for the first processed page.",
    )
    processed_image_urls: list[str] = Field(
        default_factory=list,
        description="URLs to retrieve all blurred image previews (one per uploaded file).",
    )
    evidence_preview_url: str = Field(
        description="URL to retrieve the generated evidence PDF for in-page preview."
    )
    preliminary: bool = Field(
        default=True,
        description="Always true: interpretation and calculator output are preliminary.",
    )
    actual_purchase_is_authoritative: bool = Field(
        default=True,
        description="The actual purchase is the authoritative record.",
    )
    actual_purchase_is_authoritative_text: str = Field(
        default=(
            "This interpretation and the pricing calculator are preliminary. "
            "The actual purchase is the authoritative record and determines final outcomes."
        ),
    )
    requested_overrides: QuoteOverrides | None = Field(
        default=None,
        description="Overrides requested by the client for this interpretation, if any.",
    )


# ---------------------------------------------------------------------------
# Accept endpoint  POST /api/new_laptop/{interpretation_id}/accept
# ---------------------------------------------------------------------------


class AcceptQuoteRequest(ContractModel):
    folder_id: Optional[str] = Field(
        default=None,
        description="Override Google Drive destination folder ID. Uses server-configured default when omitted.",
    )
    overrides: Optional[QuoteOverrides] = Field(
        default=None,
        description="Structured override proposal for quote interpretation adjustments.",
    )


class AcceptQuoteResponse(ContractModel):
    evidence_filename: str = Field(
        description="Evidence PDF filename, e.g. 2026-05-13T12:00:00.000Z-user@canonical.com-laptop-quote.pdf"
    )
    download_url: str = Field(
        description="URL to download the evidence PDF"
    )
