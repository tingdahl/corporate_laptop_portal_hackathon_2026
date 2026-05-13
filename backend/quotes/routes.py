from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Cookie, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from ..auth.routes import current_user_email
from ..contracts import (
    AcceptQuoteRequest,
    AcceptQuoteResponse,
    ExtractedLaptopFields,
    InterpretQuoteResponse,
)
from .details import (
    ALLOWED_MIME_TYPES,
    EVIDENCE_DIR,
    UPLOAD_DIR,
    _build_evidence_pdf,
    _evidence_filename,
    _input_filename_indexed,
    _load_blurred_pages,
    _run_interpretation,
    _save_blurred_pages,
    _sha256_hex,
    _ts_str,
)

quotes_router = APIRouter(prefix="/new_laptop", tags=["quotes"])

# Re-export constants for backwards compatibility with tests
ALLOWED_MIME_TYPES = ALLOWED_MIME_TYPES


@quotes_router.post("", response_model=InterpretQuoteResponse)
async def new_laptop(
    files: list[UploadFile] | None = File(default=None),
    currency_override: str | None = Form(default=None),
    price_override_local: str | None = Form(default=None),
    includes_tax: bool | None = Form(default=None),
    includes_shipping: bool | None = Form(default=None),
    includes_warranty: bool | None = Form(default=None),
    staff_portal_session: str | None = Cookie(default=None),
) -> InterpretQuoteResponse:
    user_email = current_user_email(staff_portal_session)

    uploads = list(files or [])
    if not uploads:
        raise HTTPException(status_code=400, detail="Missing upload field; expected 'files'")

    interpretation_id = str(uuid4())
    ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "application/pdf": ".pdf"}

    upload_items: list[dict[str, str]] = []
    interpretation_uploads: list[tuple[bytes, str]] = []
    request_file_hashes: list[str] = []
    for idx, upload in enumerate(uploads, start=1):
        mime_type = upload.content_type or ""
        if mime_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(status_code=400, detail="Only JPEG, PNG, and PDF are supported")
        content = await upload.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        original_ext = ext_map.get(mime_type, ".bin")
        original_name = Path(upload.filename or f"upload-{idx}{original_ext}").name
        request_file_hashes.append(_sha256_hex(content))
        upload_path = UPLOAD_DIR / f"{interpretation_id}-input-{idx}{original_ext}"
        upload_path.write_bytes(content)
        upload_items.append(
            {
                "path": str(upload_path),
                "original_name": original_name,
                "original_ext": original_ext,
                "mime_type": mime_type,
            }
        )
        interpretation_uploads.append((content, mime_type))

    fields, exchange_rate, pricing, compliance, blurred_pages, ts = _run_interpretation(
        interpretation_uploads,
        request_file_hashes,
        currency_override or None,
        price_override_local or None,
        includes_tax,
        includes_shipping,
        includes_warranty,
    )
    blurred_page_paths = _save_blurred_pages(interpretation_id, blurred_pages)

    meta = {
        "interpretation_id": interpretation_id,
        "user_email": user_email,
        "timestamp_utc": ts.isoformat(),
        "upload_items": upload_items,
        "blurred_page_paths": blurred_page_paths,
        "fields": fields.model_dump(mode="json"),
        "exchange_rate": exchange_rate.model_dump(mode="json"),
        "pricing": pricing.model_dump(mode="json"),
        "compliance": compliance.model_dump(mode="json"),
        "evidence_filename": _evidence_filename(user_email, ts),
        "input_filenames": [
            _input_filename_indexed(user_email, ts, item["original_ext"], idx + 1, len(upload_items))
            for idx, item in enumerate(upload_items)
        ],
    }
    (EVIDENCE_DIR / f"{interpretation_id}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    
    # Generate image URLs for all blurred pages
    processed_image_urls = [
        f"/api/new_laptop/{interpretation_id}/image/{idx}"
        for idx in range(len(blurred_page_paths))
    ]
    
    return InterpretQuoteResponse(
        interpretation_id=interpretation_id,
        fields=fields,
        exchange_rate=exchange_rate,
        pricing=pricing,
        compliance=compliance,
        processed_image_url=(processed_image_urls[0] if processed_image_urls else None),
        processed_image_urls=processed_image_urls,
        evidence_preview_url=f"/api/new_laptop/{interpretation_id}/evidence",
    )


@quotes_router.get("/{interpretation_id}/image")
def new_laptop_image(
    interpretation_id: str,
    staff_portal_session: str | None = Cookie(default=None),
) -> FileResponse:
    """Get the first blurred image (for backwards compatibility)."""
    return new_laptop_image_by_index(interpretation_id, 0, staff_portal_session)


@quotes_router.get("/{interpretation_id}/image/{page_index}")
def new_laptop_image_by_index(
    interpretation_id: str,
    page_index: int,
    staff_portal_session: str | None = Cookie(default=None),
) -> FileResponse:
    """Get a specific blurred image by index (0-based)."""
    user_email = current_user_email(staff_portal_session)
    meta_path = EVIDENCE_DIR / f"{interpretation_id}.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Interpretation not found")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("user_email") != user_email:
        raise HTTPException(status_code=403, detail="Forbidden")

    page_paths = list(meta.get("blurred_page_paths", []))
    if not page_paths:
        raise HTTPException(status_code=404, detail="No processed preview available")
    
    if page_index < 0 or page_index >= len(page_paths):
        raise HTTPException(status_code=404, detail=f"Page index {page_index} out of range")

    page_path = Path(page_paths[page_index])
    if not page_path.exists():
        raise HTTPException(status_code=404, detail="Processed preview not found")

    return FileResponse(page_path, media_type="image/png")


@quotes_router.get("/{interpretation_id}/evidence")
def new_laptop_evidence(
    interpretation_id: str,
    staff_portal_session: str | None = Cookie(default=None),
) -> FileResponse:
    user_email = current_user_email(staff_portal_session)
    meta_path = EVIDENCE_DIR / f"{interpretation_id}.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Evidence not found")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("user_email") != user_email:
        raise HTTPException(status_code=403, detail="Forbidden")

    evidence_path = Path(str(meta.get("evidence_path", "")))
    if not evidence_path.exists():
        raise HTTPException(status_code=404, detail="Evidence PDF is not generated yet")

    return FileResponse(
        evidence_path,
        media_type="application/pdf",
        filename=meta.get("evidence_filename", f"{interpretation_id}.pdf"),
    )


@quotes_router.post("/{interpretation_id}/accept", response_model=AcceptQuoteResponse)
def new_laptop_accept(
    interpretation_id: str,
    body: AcceptQuoteRequest,
    staff_portal_session: str | None = Cookie(default=None),
) -> AcceptQuoteResponse:
    user_email = current_user_email(staff_portal_session)
    meta_path = EVIDENCE_DIR / f"{interpretation_id}.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Interpretation not found")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("user_email") != user_email:
        raise HTTPException(status_code=403, detail="Forbidden")

    upload_items = list(meta.get("upload_items", []))
    if not upload_items:
        raise HTTPException(status_code=500, detail="Missing original uploaded input metadata")

    from datetime import datetime
    ts = datetime.fromisoformat(str(meta["timestamp_utc"]))
    fields = ExtractedLaptopFields.model_validate(meta["fields"])
    exchange_rate = __import__('backend.contracts', fromlist=['ExchangeRateInfo']).ExchangeRateInfo.model_validate(meta["exchange_rate"])
    pricing = __import__('backend.contracts', fromlist=['PricingCalculatorResult']).PricingCalculatorResult.model_validate(meta["pricing"])
    compliance = __import__('backend.contracts', fromlist=['ComplianceResult']).ComplianceResult.model_validate(meta["compliance"])
    blurred_pages = _load_blurred_pages(list(meta.get("blurred_page_paths", [])))

    if body.overrides:
        interpretation_uploads: list[tuple[bytes, str]] = []
        for item in upload_items:
            upload_path = Path(str(item.get("path", "")))
            if not upload_path.exists():
                raise HTTPException(status_code=404, detail=f"Uploaded input missing: {upload_path.name}")
            mime_type = str(item.get("mime_type") or "application/octet-stream")
            interpretation_uploads.append((upload_path.read_bytes(), mime_type))

        fields, exchange_rate, pricing, compliance, blurred_pages, ts = _run_interpretation(
            interpretation_uploads,
            [_sha256_hex(Path(str(item["path"])).read_bytes()) for item in upload_items],
            body.overrides.currency_override,
            body.overrides.price_override_local,
            body.overrides.includes_tax,
            body.overrides.includes_shipping,
            body.overrides.includes_warranty,
        )
        meta["timestamp_utc"] = ts.isoformat()
        meta["blurred_page_paths"] = _save_blurred_pages(interpretation_id, blurred_pages)
        meta["fields"] = fields.model_dump(mode="json")
        meta["exchange_rate"] = exchange_rate.model_dump(mode="json")
        meta["pricing"] = pricing.model_dump(mode="json")
        meta["compliance"] = compliance.model_dump(mode="json")
        meta["evidence_filename"] = _evidence_filename(user_email, ts)
        meta["input_filenames"] = [
            _input_filename_indexed(user_email, ts, str(item.get("original_ext", ".bin")), idx + 1, len(upload_items))
            for idx, item in enumerate(upload_items)
        ]

    # Generate the evidence PDF only when the user accepts.
    evidence_bytes = _build_evidence_pdf(
        blurred_pages, user_email, _ts_str(ts), fields, exchange_rate, pricing, compliance
    )
    evidence_path = EVIDENCE_DIR / f"{interpretation_id}.pdf"
    evidence_path.write_bytes(evidence_bytes)
    evidence_filename = _evidence_filename(user_email, ts)
    meta["evidence_path"] = str(evidence_path)
    meta["evidence_filename"] = evidence_filename
    
    (EVIDENCE_DIR / f"{interpretation_id}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Return response with download URL
    download_url = f"/api/new_laptop/{interpretation_id}/evidence"
    return AcceptQuoteResponse(
        evidence_filename=evidence_filename,
        download_url=download_url,
    )


@quotes_router.get("/{interpretation_id}/evidence")
def download_evidence(
    interpretation_id: str,
    staff_portal_session: str | None = Cookie(default=None),
):
    """Download the evidence PDF for an accepted quote."""
    user_email = current_user_email(staff_portal_session)
    meta_path = EVIDENCE_DIR / f"{interpretation_id}.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Interpretation not found")
    
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("user_email") != user_email:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    evidence_path = Path(str(meta.get("evidence_path", "")))
    if not evidence_path.exists():
        raise HTTPException(status_code=404, detail="Evidence PDF not found. Accept the quote first.")
    
    evidence_filename = meta.get("evidence_filename", "quote_evidence.pdf")
    
    return Response(
        content=evidence_path.read_bytes(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{evidence_filename}"'
        }
    )
