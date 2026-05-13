from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.quotes import details as quotes_details


ROOT_DIR = Path(__file__).resolve().parents[2]
TESTDATA_DIR = ROOT_DIR / "testdata"
SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf"}


@pytest.fixture(scope="module")
def test_files() -> list[Path]:
    files = sorted(p for p in TESTDATA_DIR.iterdir() if p.suffix.lower() in SUPPORTED_SUFFIXES)
    if not files:
        pytest.skip("No quote test files found in testdata/")
    return files


def _mime_for_suffix(suffix: str) -> str:
    normalized = suffix.lower()
    if normalized == ".png":
        return "image/png"
    if normalized in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if normalized == ".pdf":
        return "application/pdf"
    raise ValueError(f"Unsupported suffix: {suffix}")


@pytest.mark.integration
def test_openrouter_can_interpret_quote_samples(test_files: list[Path]) -> None:
    """
    Integration test for section 4.2 quote interpretation.

    This test is intentionally gated to avoid accidental external API calls in routine CI/local runs.
    Enable with:
      RUN_OPENROUTER_INTEGRATION=1 OPENROUTER_API_KEY=... pytest -k openrouter_can_interpret
    """
    run_live = os.getenv("RUN_OPENROUTER_INTEGRATION", "0") == "1" or os.getenv("RUN_LIVE_OPENROUTER_TEST", "0") == "1"
    if not run_live:
        pytest.skip("Set RUN_OPENROUTER_INTEGRATION=1 or RUN_LIVE_OPENROUTER_TEST=1 to run OpenRouter integration tests")

    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY is required for integration test")

    required_fields = {
        "cpu_model",
        "cpu_cores",
        "ram_gb",
        "disk_gb",
        "quoted_price",
        "includes_warranty",
        "includes_tax",
        "includes_shipping",
        "warranty_cost",
        "tax_amount",
        "shipping_cost",
        "warranty_years",
        "currency",
    }

    for sample in test_files:
        mime_type = _mime_for_suffix(sample.suffix)
        content = sample.read_bytes()

        pages = quotes_details._file_to_page_images(content, mime_type)
        page_bytes = [quotes_details._image_to_png_bytes(page) for page in pages]
        result = quotes_details._call_interpretation(page_bytes)

        missing = required_fields - set(result.keys())
        assert not missing, f"{sample.name}: missing keys {sorted(missing)}"

        currency = str(result.get("currency", "")).strip().upper()
        assert len(currency) == 3 and currency.isalpha(), (
            f"{sample.name}: expected 3-letter currency code, got {currency!r}"
        )
