from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests
from fastapi import HTTPException
from PIL import Image, ImageFilter

from ..contracts import (
    ComplianceResult,
    ExchangeRateInfo,
    ExtractedLaptopFields,
    PricingCalculatorResult,
)
from ..common import openrouter_mock

APP_BASE_DIR = Path(__file__).resolve().parents[1]
WORK_DIR = APP_BASE_DIR / "_work"
UPLOAD_DIR = WORK_DIR / "uploads"
EVIDENCE_DIR = WORK_DIR / "evidence"

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_LAPTOP_REIMBURSEMENT_USD = 2_900.0

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "")

GOOGLE_DRIVE_QUOTES_FOLDER_ID = os.getenv("GOOGLE_DRIVE_QUOTES_FOLDER_ID", "")
GOOGLE_DRIVE_QUOTE_INPUTS_FOLDER_ID = os.getenv("GOOGLE_DRIVE_QUOTE_INPUTS_FOLDER_ID", "")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def _required_specs() -> dict[str, float]:
    return {
        "min_cores": float(os.getenv("MIN_CPU_CORES", "8")),
        "min_disk_gb": float(os.getenv("MIN_DISK_GB", "256")),
        "min_ram_gb": float(os.getenv("MIN_RAM_GB", "16")),
        "max_price_usd": float(os.getenv("MAX_PRICE_USD", "2900")),
    }


def _parse_json_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


def _openrouter_call(messages: list[dict[str, Any]]) -> str:
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    if OPENROUTER_SITE_URL:
        headers["HTTP-Referer"] = OPENROUTER_SITE_URL
    if OPENROUTER_APP_NAME:
        headers["X-Title"] = OPENROUTER_APP_NAME

    resp = requests.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        headers=headers,
        json={
            "model": OPENROUTER_MODEL,
            "messages": messages,
            "response_format": {"type": "json_object"},
        },
        timeout=90,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"OpenRouter API failed: {resp.text[:300]}")
    try:
        return resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise HTTPException(status_code=502, detail="Unexpected OpenRouter response format") from exc


def _image_data_url(image_bytes: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")


def _call_pii_detection(image_bytes: bytes) -> list[dict[str, Any]]:
    if openrouter_mock.is_enabled():
        return openrouter_mock.get_pii_boxes()

    prompt = (
        "Identify any personally identifiable information (PII) in this image such as full names, "
        "addresses, phone numbers, email addresses, or order reference numbers. "
        "Return strict JSON with a single key 'boxes': an array of objects each with fields "
        "x (left edge, 0..1), y (top edge, 0..1), w (width, 0..1), h (height, 0..1). "
        "Return an empty array if no PII is found."
    )
    content = _openrouter_call([
        {"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": _image_data_url(image_bytes)}},
        ]}
    ])
    try:
        return list(_parse_json_text(content).get("boxes", []))
    except (json.JSONDecodeError, TypeError, AttributeError):
        return []


def _call_interpretation(page_images: list[bytes], currency_override: str | None = None) -> dict[str, Any]:
    if openrouter_mock.is_enabled():
        return openrouter_mock.get_interpretation()

    currency_hint = (
        f" The user has confirmed the currency is {currency_override.upper()}; use that value."
        if currency_override else ""
    )
    prompt = (
        "Analyze this laptop shopping cart and extract the purchase details."
        + currency_hint + " "
        "Return strict JSON with these exact fields (use null when a value cannot be determined): "
        "cpu_model (string|null), cpu_cores (integer|null), "
        "ram_gb (integer|null), disk_gb (integer|null), "
        "quoted_price (number|null), includes_warranty (boolean|null), includes_tax (boolean|null), "
        "includes_shipping (boolean|null), warranty_cost (number|null), tax_amount (number|null), "
        "shipping_cost (number|null), warranty_years (number|null), "
        "currency (ISO 4217 code string, required). "
        "IMPORTANT PRICING GUIDANCE: For quoted_price, prefer extracting the price that INCLUDES warranty cost "
        "but EXCLUDES taxes and shipping when multiple price options are shown. "
        "Set includes_warranty, includes_tax, includes_shipping booleans to indicate what quoted_price actually contains. "
        "Extract warranty_cost, tax_amount, shipping_cost separately when they are itemized on the quote. "
        "Disk normalization rule: disk_gb must be binary gigabytes (GiB-style). "
        "Convert TB to GB using 1024 per TB, not 1000 (for example: 1TB -> 1024, 2TB -> 2048, 0.5TB -> 512). "
        "If capacity is written as 1000GB but also described as 1TB class storage, normalize to 1024. "
        "All monetary amounts must be in the detected local currency. "
        "Important CPU rule: if cpu_model is present but cpu_cores is not explicitly shown, infer cpu_cores "
        "from your built-in hardware knowledge for that exact CPU model (for example from known Intel/AMD/Apple specs). "
        "Only return null for cpu_cores when cpu_model is missing or genuinely ambiguous. "
        "Do not leave cpu_cores null just because the core count text is absent in the image."
    )
    parts: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for page_bytes in page_images:
        parts.append({"type": "image_url", "image_url": {"url": _image_data_url(page_bytes)}})
    content = _openrouter_call([{"role": "user", "content": parts}])
    try:
        return _parse_json_text(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Model interpretation response was not valid JSON") from exc


def _exchange_rate(local_currency: str) -> float:
    if local_currency.upper() == "USD":
        return 1.0

    currency = local_currency.upper()
    providers = [
        ("open.er-api.com", "https://open.er-api.com/v6/latest/USD", None),
        ("Frankfurter API", "https://api.frankfurter.app/latest", {"from": "USD", "to": currency}),
    ]

    last_error: HTTPException | None = None
    for provider_name, url, params in providers:
        try:
            resp = requests.get(
                url,
                params=params,
                timeout=15,
                headers={"User-Agent": "staff-portal/1.0"},
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"{provider_name} did not return a valid exchange rate")

            payload = resp.json()
            rate = payload["rates"][currency]
            return float(rate)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, HTTPException) as exc:
            last_error = exc if isinstance(exc, HTTPException) else HTTPException(
                status_code=502,
                detail=f"Could not parse {currency} exchange rate from {provider_name}",
            )

    if last_error is not None:
        raise last_error
    raise HTTPException(status_code=502, detail=f"Could not fetch exchange rate for {currency}")


def _file_to_page_images(content: bytes, mime_type: str) -> list[Image.Image]:
    if mime_type == "application/pdf":
        from pdf2image import convert_from_bytes
        return convert_from_bytes(content, dpi=150)
    return [Image.open(io.BytesIO(content)).convert("RGB")]


def _image_to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _blur_pii(img: Image.Image, boxes: list[dict[str, Any]]) -> Image.Image:
    result = img.convert("RGB")
    w, h = result.size
    for box in boxes:
        try:
            x = max(0, int(float(box["x"]) * w))
            y = max(0, int(float(box["y"]) * h))
            bw = max(1, int(float(box["w"]) * w))
            bh = max(1, int(float(box["h"]) * h))
            x2 = min(w, x + bw)
            y2 = min(h, y + bh)
            region = result.crop((x, y, x2, y2))
            result.paste(region.filter(ImageFilter.GaussianBlur(radius=15)), (x, y))
        except (KeyError, TypeError, ValueError):
            continue
    return result


def _compute_pricing(fields: ExtractedLaptopFields, rate_local_per_usd: float) -> PricingCalculatorResult:
    """
    Compute pricing and reimbursement calculations.
    
    Key requirements:
    1. Price with warranty (excluding tax/shipping) - for base reimbursement calculation
    2. Total price (including everything) - for employee expense calculation
    
    We need to know the inclusion flags, but can assume 0 for amounts not included.
    """
    def to_usd(local: float | None) -> float | None:
        return round(local / rate_local_per_usd, 2) if local is not None and rate_local_per_usd else None

    if fields.quoted_price is None:
        return PricingCalculatorResult(has_missing_inputs=True)
    
    # Step 1: Calculate price with warranty, excluding tax and shipping
    # This is the base for reimbursement calculations
    if fields.includes_warranty is None:
        return PricingCalculatorResult(has_missing_inputs=True)
    
    price_with_warranty_only = fields.quoted_price
    
    # Add warranty if not included
    if not fields.includes_warranty:
        if fields.warranty_cost is None:
            return PricingCalculatorResult(has_missing_inputs=True)
        price_with_warranty_only += fields.warranty_cost
    
    # Subtract tax if it's included in the quoted price
    if fields.includes_tax is None:
        return PricingCalculatorResult(has_missing_inputs=True)
    if fields.includes_tax:
        if fields.tax_amount is None:
            return PricingCalculatorResult(has_missing_inputs=True)
        price_with_warranty_only -= fields.tax_amount
    
    # Subtract shipping if it's included in the quoted price
    if fields.includes_shipping is None:
        return PricingCalculatorResult(has_missing_inputs=True)
    if fields.includes_shipping:
        if fields.shipping_cost is None:
            return PricingCalculatorResult(has_missing_inputs=True)
        price_with_warranty_only -= fields.shipping_cost
    
    # Step 2: Calculate total price (everything included)
    total_price_local = fields.quoted_price
    
    # Add warranty if not included
    if not fields.includes_warranty:
        if fields.warranty_cost is None:
            return PricingCalculatorResult(has_missing_inputs=True)
        total_price_local += fields.warranty_cost
    
    # Add tax if not included (assume 0 if not specified)
    if not fields.includes_tax:
        total_price_local += (fields.tax_amount if fields.tax_amount is not None else 0.0)
    
    # Add shipping if not included (assume 0 if not specified)
    if not fields.includes_shipping:
        total_price_local += (fields.shipping_cost if fields.shipping_cost is not None else 0.0)
    
    # Step 3: Calculate tax and shipping components for display
    # These are the actual amounts, not whether they're included in quoted price
    tax_amount = 0.0
    shipping_amount = 0.0
    
    if fields.includes_tax:
        tax_amount = fields.tax_amount if fields.tax_amount is not None else 0.0
    else:
        tax_amount = fields.tax_amount if fields.tax_amount is not None else 0.0
    
    if fields.includes_shipping:
        shipping_amount = fields.shipping_cost if fields.shipping_cost is not None else 0.0
    else:
        shipping_amount = fields.shipping_cost if fields.shipping_cost is not None else 0.0
    
    # Convert to USD
    price_with_warranty_usd = to_usd(price_with_warranty_only)
    total_usd = to_usd(total_price_local)
    taxes_usd = to_usd(tax_amount)
    shipping_usd = to_usd(shipping_amount)
    
    if price_with_warranty_usd is None or total_usd is None or taxes_usd is None or shipping_usd is None:
        return PricingCalculatorResult(has_missing_inputs=True)

    # Calculate reimbursements
    base = min(MAX_LAPTOP_REIMBURSEMENT_USD, price_with_warranty_usd)
    tax_reimb = (base / price_with_warranty_usd) * taxes_usd if price_with_warranty_usd > 0 else 0.0
    canonical = base + shipping_usd + tax_reimb
    
    return PricingCalculatorResult(
        laptop_price_incl_warranty_usd=round(price_with_warranty_usd, 2),
        taxes_usd=round(taxes_usd, 2),
        shipping_usd=round(shipping_usd, 2),
        laptop_base_reimbursed_usd=round(base, 2),
        tax_reimbursed_usd=round(tax_reimb, 2),
        canonical_reimbursed_usd=round(canonical, 2),
        total_purchase_usd=round(total_usd, 2),
        employee_own_expense_usd=round(total_usd - canonical, 2),
        has_missing_inputs=False,
    )


def _compute_compliance_price(
    fields: ExtractedLaptopFields,
    rate_local_per_usd: float,
    includes_tax: bool | None,
    includes_shipping: bool | None,
    includes_warranty: bool | None,
) -> float | None:
    """
    Calculate the price for compliance checking: excl. shipping, incl. warranty.
    Tax can be included or excluded - we're conservative either way.
    Returns price in USD, or None if we don't have enough information.
    """
    if fields.quoted_price is None:
        return None
    
    if not rate_local_per_usd:
        return None

    # Start with quoted price
    target_price = fields.quoted_price
    
    # Determine what's actually included (use OpenRouter's detection or user override)
    warranty_included = includes_warranty if includes_warranty is not None else fields.includes_warranty
    shipping_included = includes_shipping if includes_shipping is not None else fields.includes_shipping
    
    # Must know warranty status to calculate compliance (price should include warranty)
    if warranty_included is None:
        return None
    
    # Start with quoted price
    target_price = fields.quoted_price
    
    # Handle shipping: remove if included and we know the cost
    # If shipping status unknown, assume NOT included (conservative: doesn't artificially lower the compliance price)
    if shipping_included is True:
        if fields.shipping_cost is None:
            return None  # Shipping included but amount unknown - can't calculate
        target_price -= fields.shipping_cost
    # If shipping_included is False or None, don't modify target_price
    
    # Add warranty if not included
    if not warranty_included:
        if fields.warranty_cost is None:
            return None  # Warranty not included but cost unknown
        target_price += fields.warranty_cost
    
    # Convert to USD
    return target_price / rate_local_per_usd


def _compute_compliance(
    fields: ExtractedLaptopFields,
    pricing: PricingCalculatorResult,
    rate_local_per_usd: float,
    includes_tax: bool | None,
    includes_shipping: bool | None,
    includes_warranty: bool | None,
) -> ComplianceResult:
    req = _required_specs()

    compliance_price_usd = _compute_compliance_price(
        fields, rate_local_per_usd, includes_tax, includes_shipping, includes_warranty
    )
    price_pass = (
        compliance_price_usd <= req["max_price_usd"]
        if compliance_price_usd is not None
        else None
    )
    
    # Warranty compliance: check if warranty meets 3-year requirement
    # If user overrides "Includes Minimum 3 Years Warranty", use that
    # Otherwise check if warranty_years >= 3
    if includes_warranty is not None:
        # User explicitly said whether warranty meets requirement
        warranty_pass = includes_warranty
    elif fields.warranty_years is not None:
        # Use detected warranty duration
        warranty_pass = fields.warranty_years >= 3.0
    else:
        # Unknown
        warranty_pass = None

    return ComplianceResult(
        cpu_pass=fields.cpu_cores >= req["min_cores"] if fields.cpu_cores is not None else None,
        disk_pass=fields.disk_gb >= req["min_disk_gb"] if fields.disk_gb is not None else None,
        ram_pass=fields.ram_gb >= req["min_ram_gb"] if fields.ram_gb is not None else None,
        price_pass=price_pass,
        warranty_pass=warranty_pass,
    )


def _pass_fail(v: bool | None) -> str:
    if v is None:
        return "N/A"
    return "PASS" if v else "FAIL"


def _build_evidence_pdf(
    blurred_images: list[Image.Image],
    user_email: str,
    ts_str: str,
    fields: ExtractedLaptopFields,
    exchange_rate: ExchangeRateInfo,
    pricing: PricingCalculatorResult,
    compliance: ComplianceResult,
) -> bytes:
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.platypus import Table, TableStyle

    page_w, page_h = A4
    margin = 15 * mm
    usable_w = page_w - 2 * margin
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle("Laptop Quote Evidence")

    for img in blurred_images:
        img_w, img_h = img.size
        scale = min(usable_w / img_w, (page_h - 2 * margin) / img_h)
        draw_w = img_w * scale
        draw_h = img_h * scale
        img_buf = io.BytesIO()
        img.convert("RGB").save(img_buf, format="PNG")
        img_buf.seek(0)
        c.drawImage(
            ImageReader(img_buf),
            margin, page_h - margin - draw_h,
            width=draw_w, height=draw_h,
        )
        c.showPage()

    currency = fields.currency
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, page_h - margin - 20, "Laptop Quote Evidence")

    # Helper to format boolean flags
    def fmt_bool(val: bool | None) -> str:
        if val is None:
            return "Unknown"
        return "Yes" if val else "No"

    table_data = [
        ["Field", "Value", "Status"],
        ["Timestamp (UTC)", ts_str, ""],
        ["User", user_email, ""],
        ["CPU", f"{fields.cpu_model or 'N/A'} ({fields.cpu_cores or 'N/A'} cores)", _pass_fail(compliance.cpu_pass)],
        ["RAM", f"{fields.ram_gb or 'N/A'} GB", _pass_fail(compliance.ram_pass)],
        ["Disk", f"{fields.disk_gb or 'N/A'} GB", _pass_fail(compliance.disk_pass)],
        ["Warranty", f"{fields.warranty_years or 'N/A'} years (min 3)", _pass_fail(compliance.warranty_pass)],
        ["Quoted Price", f"{fields.quoted_price or 'N/A'} {currency}", ""],
        ["Includes Warranty", fmt_bool(fields.includes_warranty), ""],
        ["Includes Tax", fmt_bool(fields.includes_tax), ""],
        ["Includes Shipping", fmt_bool(fields.includes_shipping), ""],
        ["Warranty Cost", f"{fields.warranty_cost or 'N/A'} {currency}", ""],
        ["Tax Amount", f"{fields.tax_amount or 'N/A'} {currency}", ""],
        ["Shipping Cost", f"{fields.shipping_cost or 'N/A'} {currency}", ""],
        ["Exchange rate", f"1 USD = {exchange_rate.rate_local_per_usd:.6f} {currency} @ {ts_str}", ""],
        ["Canonical reimbursed", f"{pricing.canonical_reimbursed_usd or 'N/A'} USD", _pass_fail(compliance.price_pass)],
        ["Employee own expense", f"{pricing.employee_own_expense_usd or 'N/A'} USD", ""],
        ["Preliminary notice", "Interpretation and calculator are preliminary. The actual purchase is authoritative.", ""],
    ]

    col_widths = [usable_w * 0.32, usable_w * 0.52, usable_w * 0.16]
    tbl = Table(table_data, colWidths=col_widths)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#333333")),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#f5f5f5")]),
        ("GRID", (0, 0), (-1, -1), 0.25, rl_colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    tbl_w, tbl_h = tbl.wrapOn(c, usable_w, page_h)
    tbl.drawOn(c, margin, page_h - margin - 36 - tbl_h)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def _ts_str(ts: datetime) -> str:
    return ts.strftime(f"%Y-%m-%dT%H:%M:%S.{ts.microsecond // 1000:03d}Z")


def _evidence_filename(user_email: str, ts: datetime) -> str:
    return f"{_ts_str(ts)}-{user_email}-laptop-quote.pdf"


def _input_filename(user_email: str, ts: datetime, original_ext: str) -> str:
    return f"{_ts_str(ts)}-{user_email}-laptop-quote-input{original_ext}"


def _input_filename_indexed(user_email: str, ts: datetime, original_ext: str, index: int, total: int) -> str:
    if total <= 1:
        return _input_filename(user_email, ts, original_ext)
    return f"{_ts_str(ts)}-{user_email}-laptop-quote-input-{index}{original_ext}"


def _save_blurred_pages(interpretation_id: str, blurred_pages: list[Image.Image]) -> list[str]:
    page_paths: list[str] = []
    for idx, page in enumerate(blurred_pages, start=1):
        page_path = EVIDENCE_DIR / f"{interpretation_id}-page-{idx}.png"
        page.convert("RGB").save(page_path, format="PNG")
        page_paths.append(str(page_path))
    return page_paths


def _load_blurred_pages(page_paths: list[str]) -> list[Image.Image]:
    pages: list[Image.Image] = []
    for page_path in page_paths:
        path = Path(page_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Processed preview page missing: {path.name}")
        pages.append(Image.open(path).convert("RGB"))
    return pages


def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _int_or_none(v: Any) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _float_or_none(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _bool_or_none(v: Any) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("true", "1", "yes")
    return bool(v)


def _run_interpretation(
    uploads: list[tuple[bytes, str]],
    request_file_hashes: list[str],
    currency_override: str | None,
    price_override_local: str | None,
    includes_tax: bool | None,
    includes_shipping: bool | None,
    includes_warranty: bool | None,
) -> tuple[
    ExtractedLaptopFields,
    ExchangeRateInfo,
    PricingCalculatorResult,
    ComplianceResult,
    list[Image.Image],
    datetime,
]:
    ts = datetime.now(timezone.utc)
    if not uploads:
        raise HTTPException(status_code=400, detail="No files supplied for interpretation")

    pages: list[Image.Image] = []
    for content, mime_type in uploads:
        pages.extend(_file_to_page_images(content, mime_type))

    blurred_pages: list[Image.Image] = []
    try:
        if request_file_hashes:
            openrouter_mock.set_request_file_hashes(request_file_hashes)

        for page in pages:
            page_bytes = _image_to_png_bytes(page)
            boxes = _call_pii_detection(page_bytes)
            blurred_pages.append(_blur_pii(page, boxes))
        blurred_bytes_list = [_image_to_png_bytes(p) for p in blurred_pages]
        raw = _call_interpretation(blurred_bytes_list, currency_override=currency_override)
        currency = (currency_override or str(raw.get("currency") or "USD")).upper()
        
        # Apply price override if provided
        quoted_price = _float_or_none(raw.get("quoted_price"))
        if price_override_local:
            try:
                quoted_price = float(price_override_local)
            except (ValueError, TypeError):
                pass  # Keep detected value if override is invalid
        
        fields = ExtractedLaptopFields(
            cpu_model=raw.get("cpu_model") or None,
            cpu_cores=_int_or_none(raw.get("cpu_cores")),
            ram_gb=_int_or_none(raw.get("ram_gb")),
            disk_gb=_int_or_none(raw.get("disk_gb")),
            quoted_price=quoted_price,
            includes_warranty=_bool_or_none(raw.get("includes_warranty")),
            includes_tax=_bool_or_none(raw.get("includes_tax")),
            includes_shipping=_bool_or_none(raw.get("includes_shipping")),
            warranty_cost=_float_or_none(raw.get("warranty_cost")),
            tax_amount=_float_or_none(raw.get("tax_amount")),
            shipping_cost=_float_or_none(raw.get("shipping_cost")),
            warranty_years=_float_or_none(raw.get("warranty_years")),
            currency=currency,
        )
        
        # Apply user overrides to fields for pricing calculation
        fields_with_overrides = fields.model_copy(update={
            k: v for k, v in {
                "includes_warranty": includes_warranty,
                "includes_tax": includes_tax,
                "includes_shipping": includes_shipping,
            }.items() if v is not None
        })
        
        rate = _exchange_rate(currency)
        exchange_rate = ExchangeRateInfo(currency=currency, rate_local_per_usd=rate, captured_at_utc=ts)
        pricing = _compute_pricing(fields_with_overrides, rate)
        compliance = _compute_compliance(fields_with_overrides, pricing, rate, includes_tax, includes_shipping, includes_warranty)
        return fields_with_overrides, exchange_rate, pricing, compliance, blurred_pages, ts
    finally:
        openrouter_mock.clear_request_file_hashes()
