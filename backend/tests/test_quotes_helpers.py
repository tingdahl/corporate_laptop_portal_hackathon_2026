"""
Unit tests for quote helper functions in backend/quotes/details.py
"""
import json
from datetime import datetime, timezone
from io import BytesIO

import pytest
from PIL import Image

from backend.quotes import details as quote_details


class TestParseJsonText:
    """Test JSON parsing with various input formats."""

    def test_parse_clean_json(self):
        """Parse well-formed JSON."""
        text = '{"key": "value", "number": 42}'
        result = quote_details._parse_json_text(text)
        assert result == {"key": "value", "number": 42}

    def test_parse_json_with_markdown_fence(self):
        """Parse JSON wrapped in markdown code fence."""
        text = '```json\n{"key": "value"}\n```'
        result = quote_details._parse_json_text(text)
        assert result == {"key": "value"}

    def test_parse_json_with_plain_fence(self):
        """Parse JSON wrapped in plain code fence."""
        text = '```\n{"key": "value"}\n```'
        result = quote_details._parse_json_text(text)
        assert result == {"key": "value"}

    def test_parse_json_with_whitespace(self):
        """Parse JSON with leading/trailing whitespace."""
        text = '  \n  {"key": "value"}  \n  '
        result = quote_details._parse_json_text(text)
        assert result == {"key": "value"}

    def test_parse_invalid_json_raises_error(self):
        """Invalid JSON raises JSONDecodeError."""
        import json
        text = '{"invalid": json}'
        with pytest.raises(json.JSONDecodeError):
            quote_details._parse_json_text(text)


class TestPassFail:
    """Test pass/fail status formatter."""

    def test_pass(self):
        assert quote_details._pass_fail(True) == "PASS"

    def test_fail(self):
        assert quote_details._pass_fail(False) == "FAIL"

    def test_none(self):
        assert quote_details._pass_fail(None) == "N/A"


class TestFilenameGeneration:
    """Test filename generation functions."""

    def test_ts_str_format(self):
        """Timestamp string should be ISO 8601 with milliseconds."""
        ts = datetime(2026, 5, 13, 14, 30, 45, 123456, tzinfo=timezone.utc)
        result = quote_details._ts_str(ts)
        assert result == "2026-05-13T14:30:45.123Z"

    def test_evidence_filename(self):
        """Evidence filename format."""
        ts = datetime(2026, 5, 13, 14, 30, 45, 123456, tzinfo=timezone.utc)
        email = "user@canonical.com"
        result = quote_details._evidence_filename(email, ts)
        assert result == "2026-05-13T14:30:45.123Z-user@canonical.com-laptop-quote.pdf"

    def test_input_filename(self):
        """Input filename format."""
        ts = datetime(2026, 5, 13, 14, 30, 45, 123456, tzinfo=timezone.utc)
        email = "user@canonical.com"
        result = quote_details._input_filename(email, ts, ".png")
        assert result == "2026-05-13T14:30:45.123Z-user@canonical.com-laptop-quote-input.png"

    def test_input_filename_indexed_single_file(self):
        """Indexed filename with single file."""
        ts = datetime(2026, 5, 13, 14, 30, 45, 123456, tzinfo=timezone.utc)
        email = "user@canonical.com"
        result = quote_details._input_filename_indexed(email, ts, ".jpg", 1, 1)
        # Single file doesn't get index suffix
        assert result == "2026-05-13T14:30:45.123Z-user@canonical.com-laptop-quote-input.jpg"

    def test_input_filename_indexed_multiple_files(self):
        """Indexed filename with multiple files."""
        ts = datetime(2026, 5, 13, 14, 30, 45, 123456, tzinfo=timezone.utc)
        email = "user@canonical.com"
        result1 = quote_details._input_filename_indexed(email, ts, ".png", 1, 3)
        result2 = quote_details._input_filename_indexed(email, ts, ".jpg", 2, 3)
        result3 = quote_details._input_filename_indexed(email, ts, ".pdf", 3, 3)
        assert result1 == "2026-05-13T14:30:45.123Z-user@canonical.com-laptop-quote-input-1.png"
        assert result2 == "2026-05-13T14:30:45.123Z-user@canonical.com-laptop-quote-input-2.jpg"
        assert result3 == "2026-05-13T14:30:45.123Z-user@canonical.com-laptop-quote-input-3.pdf"


class TestImageDataUrl:
    """Test base64 image encoding."""

    def test_image_data_url(self):
        """Generate base64 data URL for image bytes."""
        # Create minimal valid PNG (1x1 black pixel)
        img = Image.new("RGB", (1, 1), color="black")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()
        
        result = quote_details._image_data_url(image_bytes)
        
        assert result.startswith("data:image/png;base64,")
        assert len(result) > 40  # Should have substantial base64 content


class TestImageToPngBytes:
    """Test image to PNG bytes conversion."""

    def test_convert_rgb_image(self):
        """Convert RGB image to PNG bytes."""
        img = Image.new("RGB", (100, 100), color="red")
        result = quote_details._image_to_png_bytes(img)
        
        assert isinstance(result, bytes)
        assert result[:8] == b'\x89PNG\r\n\x1a\n'  # PNG signature

    def test_convert_rgba_image(self):
        """Convert RGBA image to PNG bytes."""
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        result = quote_details._image_to_png_bytes(img)
        
        assert isinstance(result, bytes)
        assert result[:8] == b'\x89PNG\r\n\x1a\n'  # PNG signature


class TestBlurPii:
    """Test PII blurring on images."""

    def test_blur_single_box(self):
        """Blur a single region."""
        img = Image.new("RGB", (200, 200), color="white")
        boxes = [{"x": 50, "y": 50, "w": 100, "h": 50}]
        
        result = quote_details._blur_pii(img, boxes)
        
        assert result.size == (200, 200)
        assert result.mode == "RGB"
        # Can't easily test blur effect without pixel inspection

    def test_blur_multiple_boxes(self):
        """Blur multiple regions."""
        img = Image.new("RGB", (300, 300), color="white")
        boxes = [
            {"x": 10, "y": 10, "w": 50, "h": 50},
            {"x": 100, "y": 100, "w": 80, "h": 60},
            {"x": 200, "y": 200, "w": 50, "h": 50},
        ]
        
        result = quote_details._blur_pii(img, boxes)
        
        assert result.size == (300, 300)
        assert result.mode == "RGB"

    def test_blur_empty_boxes(self):
        """No boxes returns original image."""
        img = Image.new("RGB", (100, 100), color="blue")
        boxes = []
        
        result = quote_details._blur_pii(img, boxes)
        
        # Should return a copy of the image
        assert result.size == (100, 100)
        assert result.mode == "RGB"

    def test_blur_out_of_bounds_box(self):
        """Handle boxes that extend beyond image bounds."""
        img = Image.new("RGB", (100, 100), color="green")
        boxes = [{"x": 80, "y": 80, "w": 50, "h": 50}]  # Extends to (130, 130)
        
        result = quote_details._blur_pii(img, boxes)
        
        # Should handle gracefully
        assert result.size == (100, 100)


class TestFileToPageImages:
    """Test file conversion to page images."""

    def test_convert_png_image(self):
        """Convert PNG file to page images."""
        img = Image.new("RGB", (800, 600), color="red")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()
        
        result = quote_details._file_to_page_images(content, "image/png")
        
        assert len(result) == 1
        assert result[0].size == (800, 600)

    def test_convert_jpeg_image(self):
        """Convert JPEG file to page images."""
        img = Image.new("RGB", (1024, 768), color="blue")
        buffer = BytesIO()
        img.save(buffer, format="JPEG")
        content = buffer.getvalue()
        
        result = quote_details._file_to_page_images(content, "image/jpeg")
        
        assert len(result) == 1
        assert result[0].size == (1024, 768)

    def test_invalid_mime_type_raises_error(self):
        """Invalid content raises UnidentifiedImageError."""
        from PIL import UnidentifiedImageError
        content = b"fake content"
        
        with pytest.raises(UnidentifiedImageError):
            quote_details._file_to_page_images(content, "application/json")

    def test_corrupted_image_raises_error(self):
        """Corrupted image data raises error."""
        content = b"not an image"
        
        with pytest.raises(Exception):  # PIL raises various exceptions
            quote_details._file_to_page_images(content, "image/png")


class TestRequiredSpecs:
    """Test required specifications retrieval."""

    def test_required_specs_structure(self):
        """Required specs have correct structure."""
        specs = quote_details._required_specs()
        
        assert "min_cores" in specs
        assert "min_ram_gb" in specs
        assert "min_disk_gb" in specs
        assert "max_price_usd" in specs
        
        # All should be numeric
        assert isinstance(specs["min_cores"], (int, float))
        assert isinstance(specs["min_ram_gb"], (int, float))
        assert isinstance(specs["min_disk_gb"], (int, float))
        assert isinstance(specs["max_price_usd"], (int, float))

    def test_required_specs_reasonable_values(self):
        """Required specs have reasonable values."""
        specs = quote_details._required_specs()
        
        assert specs["min_cores"] > 0
        assert specs["min_ram_gb"] > 0
        assert specs["min_disk_gb"] > 0
        assert specs["max_price_usd"] > 0
        assert specs["max_price_usd"] < 10000  # Reasonable upper bound
