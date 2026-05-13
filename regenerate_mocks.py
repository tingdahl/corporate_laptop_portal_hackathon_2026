#!/usr/bin/env python3
"""
Regenerate OpenRouter mock fixtures with new pricing field structure.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from backend.quotes_routes import _call_pii_detection, _call_interpretation, _file_to_page_images, _image_to_png_bytes


# Test cases mapping
TEST_CASES = {
    "user1": [
        "testdata/user1/Screenshot from 2026-03-12 22-21-43.png",
        "testdata/user1/Screenshot from 2026-03-12 22-34-08.png",
    ],
    "user2": ["testdata/user2/specs.png"],
    "user3": ["testdata/user3/DellXPS_Order.png"],
    "user4": ["testdata/user4/thinkpadT16Gen4_i7_32G_1T.png"],
    "user5": ["testdata/user5/specs.png"],
    "user6": [
        "testdata/user6/Spec.png",
        "testdata/user6/奇藝科技-報價單科能PA14250V3-0127.pdf",
    ],
}


def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def regenerate_mock_for_user(user: str, file_paths: list[str]) -> dict:
    """Generate mock data for a user by calling OpenRouter API."""
    print(f"\n{'=' * 60}")
    print(f"Processing {user}: {len(file_paths)} file(s)")
    print(f"{'=' * 60}")
    
    # Load files and extract pages
    pages = []
    file_hashes = []
    for file_path in file_paths:
        print(f"  Loading: {file_path}")
        path = Path(file_path)
        if not path.exists():
            print(f"    ⚠️  File not found: {file_path}")
            continue
        
        content = path.read_bytes()
        file_hashes.append(_sha256_hex(content))
        
        # Determine MIME type
        if file_path.lower().endswith('.png'):
            mime_type = 'image/png'
        elif file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg'):
            mime_type = 'image/jpeg'
        elif file_path.lower().endswith('.pdf'):
            mime_type = 'application/pdf'
        else:
            print(f"    ⚠️  Unknown file type")
            continue
        
        file_pages = _file_to_page_images(content, mime_type)
        pages.extend(file_pages)
        print(f"    ✓ Extracted {len(file_pages)} page(s)")
    
    if not pages:
        print(f"  ❌ No pages extracted for {user}")
        return None
    
    # Call PII detection for each page
    print(f"\n  Calling PII detection on {len(pages)} page(s)...")
    pii_boxes = []
    for idx, page in enumerate(pages, 1):
        page_bytes = _image_to_png_bytes(page)
        boxes = _call_pii_detection(page_bytes)
        pii_boxes.extend(boxes)
        print(f"    Page {idx}: {len(boxes)} PII box(es) detected")
    
    # Blur pages (we'll use blurred for interpretation to match production)
    from backend.quotes_routes import _blur_pii
    blurred_pages = []
    for page in pages:
        page_bytes = _image_to_png_bytes(page)
        boxes = _call_pii_detection(page_bytes)
        blurred_pages.append(_blur_pii(page, boxes))
    
    blurred_bytes_list = [_image_to_png_bytes(p) for p in blurred_pages]
    
    # Call interpretation
    print(f"\n  Calling OpenRouter interpretation...")
    raw = _call_interpretation(blurred_bytes_list, currency_override=None)
    print(f"    ✓ Received response")
    
    # Build mock structure
    mock_data = {
        "user": user,
        "files": file_paths,
        "file_count": len(file_paths),
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash"),
        "pii_detection": {
            "boxes": pii_boxes,
        },
        "interpretation": raw,
        "file_hashes": file_hashes,
    }
    
    return mock_data


def main():
    print("\n" + "=" * 60)
    print("OpenRouter Mock Regeneration")
    print("=" * 60)
    
    # Disable mocking to force real API calls
    if os.getenv("OPENROUTER_MOCK_ENABLED"):
        print("\n⚠️  OPENROUTER_MOCK_ENABLED was set - disabling it for regeneration")
        os.environ["OPENROUTER_MOCK_ENABLED"] = "0"
    
    # Check for API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("\n❌ ERROR: OPENROUTER_API_KEY not set in environment")
        print("   Please run: source .env")
        return 1
    
    print(f"\n✓ API Key found")
    print(f"✓ Model: {os.getenv('OPENROUTER_MODEL', 'google/gemini-2.5-flash')}")
    
    output_dir = Path("testdata/openrouter_mock")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {}
    failed = []
    
    for user, file_paths in TEST_CASES.items():
        try:
            mock_data = regenerate_mock_for_user(user, file_paths)
            if mock_data:
                # Save to file
                output_file = output_dir / f"{user}_response.json"
                output_file.write_text(json.dumps(mock_data, indent=2, ensure_ascii=False), encoding='utf-8')
                print(f"\n  ✓ Saved to: {output_file}")
                results[user] = mock_data
            else:
                failed.append(user)
        except Exception as e:
            print(f"\n  ❌ Error processing {user}: {e}")
            import traceback
            traceback.print_exc()
            failed.append(user)
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"✓ Successfully processed: {len(results)} user(s)")
    if failed:
        print(f"❌ Failed: {len(failed)} user(s) - {', '.join(failed)}")
    else:
        print(f"✓ All users processed successfully")
    
    # Show field analysis
    if results:
        print("\n" + "=" * 60)
        print("Field Analysis")
        print("=" * 60)
        print(f"{'User':<10} {'quoted_price':<15} {'incl_warranty':<15} {'incl_tax':<12} {'incl_ship':<12}")
        print("-" * 70)
        for user, data in results.items():
            interp = data["interpretation"]
            print(f"{user:<10} {str(interp.get('quoted_price')):<15} {str(interp.get('includes_warranty')):<15} {str(interp.get('includes_tax')):<12} {str(interp.get('includes_shipping')):<12}")
    
    return 0 if not failed else 1


if __name__ == "__main__":
    exit(main())
