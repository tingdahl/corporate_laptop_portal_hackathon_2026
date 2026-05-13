# OpenRouter Mock Fixtures

This directory contains captured OpenRouter API responses for test cases.

## Structure

Each `user*_response.json` file contains:
- **user**: Test user identifier
- **files**: Source files used for this test case
- **file_count**: Number of files  
- **captured_at_utc**: Timestamp when captured
- **model**: OpenRouter model used
- **pii_detection**: PII boxes detected in the images
- **interpretation**: Extracted laptop quote fields
- **file_hashes**: SHA-256 hashes of input files for content-based mock selection

## Field Structure (Updated May 2026)

The interpretation object contains:
- **Hardware specs**: `cpu_model`, `cpu_cores`, `ram_gb`, `disk_gb`
- **Pricing**: `quoted_price`, `currency`
- **Inclusions**: `includes_warranty`, `includes_tax`, `includes_shipping` (booleans)
- **Itemized costs**: `warranty_cost`, `tax_amount`, `shipping_cost` (when separately listed)
- **Warranty**: `warranty_years`

## Regenerating Fixtures

To regenerate all fixtures with fresh OpenRouter API calls:

```bash
source .env
python regenerate_mocks.py
```

This will:
1. Disable mocking temporarily
2. Call OpenRouter API for each test case
3. Update all `user*_response.json` files
4. Display field analysis summary

## Pricing Model

OpenRouter is instructed to prefer extracting:
- **quoted_price**: WITH warranty, WITHOUT taxes, WITHOUT shipping

The boolean flags indicate what the quoted_price actually contains, and separate itemized amounts are captured when available.
