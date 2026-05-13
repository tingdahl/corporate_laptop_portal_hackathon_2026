"""Quotes management module."""
from .routes import quotes_router
from .details import (
    _required_specs,
    _compute_compliance_price,
    _compute_compliance,
    _file_to_page_images,
    _image_to_png_bytes,
)

__all__ = [
    "quotes_router",
    "_required_specs",
    "_compute_compliance_price",
    "_compute_compliance",
    "_file_to_page_images",
    "_image_to_png_bytes",
]
