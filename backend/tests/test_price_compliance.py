"""
Unit tests for price compliance logic with simplified pricing model.
Compliance rule: Price WITH warranty, EXCLUDING shipping, must be under threshold.
Tax can be included or excluded - we're conservative either way.
"""
import pytest

from backend.contracts.quotes import ExtractedLaptopFields, PricingCalculatorResult
from backend.quotes.details import _compute_compliance_price, _compute_compliance, _required_specs


# Test data constants
USD_RATE = 1.0
EUR_RATE = 0.85  # 1 USD = 0.85 EUR


# Get actual requirements from environment/config
SPECS = _required_specs()


class TestComputeCompliancePrice:
    """Test the _compute_compliance_price function that calculates price for compliance checking."""

    def test_warranty_included_no_shipping(self):
        """Quoted price includes warranty, excludes shipping - perfect match for compliance check."""
        fields = ExtractedLaptopFields(
            cpu_model="Intel i7",
            cpu_cores=12,
            ram_gb=32,
            disk_gb=1024,
            quoted_price=2500.0,  # USD
            includes_warranty=True,
            includes_tax=False,
            includes_shipping=False,
            warranty_cost=None,
            tax_amount=None,
            shipping_cost=None,
            warranty_years=3.0,
            currency="USD",
        )
        result = _compute_compliance_price(
            fields,
            rate_local_per_usd=USD_RATE,
            includes_tax=None,  # Not needed for this case
            includes_shipping=None,  # Override from user
            includes_warranty=None,  # Override from user
        )
        # Price already in correct format
        assert result == pytest.approx(2500.0, rel=0.01)

    def test_warranty_and_shipping_included_need_to_subtract_shipping(self):
        """Quoted price includes both warranty and shipping - must subtract shipping."""
        fields = ExtractedLaptopFields(
            cpu_model="Intel i7",
            cpu_cores=12,
            ram_gb=32,
            disk_gb=1024,
            quoted_price=2600.0,  # EUR, includes warranty and shipping
            includes_warranty=True,
            includes_tax=False,
            includes_shipping=True,
            warranty_cost=None,
            tax_amount=None,
            shipping_cost=100.0,
            warranty_years=3.0,
            currency="EUR",
        )
        result = _compute_compliance_price(
            fields,
            rate_local_per_usd=EUR_RATE,
            includes_tax=None,
            includes_shipping=None,
            includes_warranty=None,
        )
        # 2600 - 100 (shipping) = 2500 EUR
        # 2500 / 0.85 = 2941.18 USD
        assert result == pytest.approx(2941.18, rel=0.01)

    def test_warranty_not_included_must_add_it(self):
        """Quoted price excludes warranty - must add warranty cost."""
        fields = ExtractedLaptopFields(
            cpu_model="Intel i9",
            cpu_cores=16,
            ram_gb=64,
            disk_gb=2048,
            quoted_price=2400.0,  # USD, no warranty
            includes_warranty=False,
            includes_tax=False,
            includes_shipping=False,
            warranty_cost=200.0,
            tax_amount=None,
            shipping_cost=None,
            warranty_years=3.0,
            currency="USD",
        )
        result = _compute_compliance_price(
            fields,
            rate_local_per_usd=USD_RATE,
            includes_tax=None,
            includes_shipping=None,
            includes_warranty=None,
        )
        # 2400 + 200 (warranty) = 2600 USD
        assert result == pytest.approx(2600.0, rel=0.01)

    def test_warranty_not_included_but_cost_unknown(self):
        """Warranty not included and cost unknown - cannot calculate."""
        fields = ExtractedLaptopFields(
            cpu_model="Intel i7",
            cpu_cores=12,
            ram_gb=32,
            disk_gb=1024,
            quoted_price=2500.0,
            includes_warranty=False,
            includes_tax=False,
            includes_shipping=False,
            warranty_cost=None,  # Unknown!
            tax_amount=None,
            shipping_cost=None,
            warranty_years=3.0,
            currency="USD",
        )
        result = _compute_compliance_price(
            fields,
            rate_local_per_usd=USD_RATE,
            includes_tax=None,
            includes_shipping=None,
            includes_warranty=None,
        )
        assert result is None, "Cannot add unknown warranty cost"

    def test_shipping_included_but_amount_unknown(self):
        """Shipping included but amount unknown - cannot calculate."""
        fields = ExtractedLaptopFields(
            cpu_model="Intel i7",
            cpu_cores=12,
            ram_gb=32,
            disk_gb=1024,
            quoted_price=2500.0,
            includes_warranty=True,
            includes_tax=False,
            includes_shipping=True,
            warranty_cost=None,
            tax_amount=None,
            shipping_cost=None,  # Unknown!
            warranty_years=3.0,
            currency="USD",
        )
        result = _compute_compliance_price(
            fields,
            rate_local_per_usd=USD_RATE,
            includes_tax=None,
            includes_shipping=None,
            includes_warranty=None,
        )
        assert result is None, "Cannot subtract unknown shipping cost"

    def test_warranty_status_unknown(self):
        """Don't know if warranty is included - cannot calculate."""
        fields = ExtractedLaptopFields(
            cpu_model="Intel i7",
            cpu_cores=12,
            ram_gb=32,
            disk_gb=1024,
            quoted_price=2500.0,
            includes_warranty=None,  # Unknown!
            includes_tax=False,
            includes_shipping=False,
            warranty_cost=200.0,
            tax_amount=None,
            shipping_cost=None,
            warranty_years=3.0,
            currency="USD",
        )
        result = _compute_compliance_price(
            fields,
            rate_local_per_usd=USD_RATE,
            includes_tax=None,
            includes_shipping=None,
            includes_warranty=None,
        )
        assert result is None, "Cannot determine without knowing warranty status"

    def test_shipping_status_unknown(self):
        """When shipping status unknown, assume NOT included (conservative)."""
        fields = ExtractedLaptopFields(
            cpu_model="Intel i7",
            cpu_cores=12,
            ram_gb=32,
            disk_gb=1024,
            quoted_price=2500.0,
            includes_warranty=True,
            includes_tax=False,
            includes_shipping=None,  # Unknown - assume not included
            warranty_cost=None,
            tax_amount=None,
            shipping_cost=100.0,
            warranty_years=3.0,
            currency="USD",
        )
        result = _compute_compliance_price(
            fields,
            rate_local_per_usd=USD_RATE,
            includes_tax=None,
            includes_shipping=None,
            includes_warranty=None,
        )
        # Conservative: assume shipping NOT included, so price stays as-is
        assert result == pytest.approx(2500.0, rel=0.01)

    def test_quoted_price_missing(self):
        """No quoted price - cannot calculate."""
        fields = ExtractedLaptopFields(
            cpu_model="Intel i7",
            cpu_cores=12,
            ram_gb=32,
            disk_gb=1024,
            quoted_price=None,  # Missing!
            includes_warranty=True,
            includes_tax=False,
            includes_shipping=False,
            warranty_cost=None,
            tax_amount=None,
            shipping_cost=None,
            warranty_years=3.0,
            currency="USD",
        )
        result = _compute_compliance_price(
            fields,
            rate_local_per_usd=USD_RATE,
            includes_tax=None,
            includes_shipping=None,
            includes_warranty=None,
        )
        assert result is None, "Cannot calculate without quoted price"

    def test_user_override_takes_precedence(self):
        """User overrides should override OpenRouter's detection."""
        fields = ExtractedLaptopFields(
            cpu_model="Intel i7",
            cpu_cores=12,
            ram_gb=32,
            disk_gb=1024,
            quoted_price=2600.0,  # USD
            includes_warranty=True,  # OpenRouter thinks warranty included
            includes_tax=False,
            includes_shipping=True,  # OpenRouter thinks shipping included
            warranty_cost=None,
            tax_amount=None,
            shipping_cost=100.0,
            warranty_years=3.0,
            currency="USD",
        )
        # User overrides: shipping NOT included
        result = _compute_compliance_price(
            fields,
            rate_local_per_usd=USD_RATE,
            includes_tax=None,
            includes_shipping=False,  # User says no shipping
            includes_warranty=None,
        )
        # No shipping to subtract, price as-is
        assert result == pytest.approx(2600.0, rel=0.01)

    def test_tax_included_is_conservative(self):
        """Tax being included or not doesn't affect compliance check (conservative)."""
        fields = ExtractedLaptopFields(
            cpu_model="Intel i7",
            cpu_cores=12,
            ram_gb=32,
            disk_gb=1024,
            quoted_price=2500.0,  # USD, may or may not include tax
            includes_warranty=True,
            includes_tax=True,  # Includes tax
            includes_shipping=False,
            warranty_cost=None,
            tax_amount=200.0,
            shipping_cost=None,
            warranty_years=3.0,
            currency="USD",
        )
        result = _compute_compliance_price(
            fields,
            rate_local_per_usd=USD_RATE,
            includes_tax=None,
            includes_shipping=None,
            includes_warranty=None,
        )
        # Tax doesn't matter for compliance - we're conservative
        # If price with tax is under limit, price without tax will be too
        assert result == pytest.approx(2500.0, rel=0.01)

    def test_complex_foreign_currency_scenario(self):
        """Complex case: warranty not included, shipping included, foreign currency."""
        fields = ExtractedLaptopFields(
            cpu_model="Intel i9",
            cpu_cores=16,
            ram_gb=64,
            disk_gb=2048,
            quoted_price=2200.0,  # EUR, no warranty, with shipping
            includes_warranty=False,
            includes_tax=True,
            includes_shipping=True,
            warranty_cost=150.0,
            tax_amount=300.0,
            shipping_cost=100.0,
            warranty_years=4.0,
            currency="EUR",
        )
        result = _compute_compliance_price(
            fields,
            rate_local_per_usd=EUR_RATE,
            includes_tax=None,
            includes_shipping=None,
            includes_warranty=None,
        )
        # 2200 - 100 (shipping) + 150 (warranty) = 2250 EUR
        # 2250 / 0.85 = 2647.06 USD
        assert result == pytest.approx(2647.06, rel=0.01)


class TestComputeCompliance:
    """Test the full _compute_compliance function with price logic integration."""

    def test_price_pass_when_under_limit(self):
        """Price compliance passes when calculated price is under the limit."""
        fields = ExtractedLaptopFields(
            cpu_model="Intel i7",
            cpu_cores=int(SPECS["min_cores"]) + 2,
            ram_gb=int(SPECS["min_ram_gb"]) + 16,
            disk_gb=int(SPECS["min_disk_gb"]) + 512,
            quoted_price=2400.0,  # USD
            includes_warranty=True,
            includes_tax=False,
            includes_shipping=False,
            warranty_cost=None,
            tax_amount=None,
            shipping_cost=None,
            warranty_years=3.0,
            currency="USD",
        )
        pricing = PricingCalculatorResult(has_missing_inputs=False)
        
        compliance = _compute_compliance(
            fields,
            pricing,
            rate_local_per_usd=USD_RATE,
            includes_tax=None,
            includes_shipping=None,
            includes_warranty=None,
        )
        # 2400 USD < 2900 USD limit
        assert compliance.price_pass is True

    def test_price_fail_when_over_limit(self):
        """Price compliance fails when calculated price exceeds the limit."""
        fields = ExtractedLaptopFields(
            cpu_model="Intel i9",
            cpu_cores=int(SPECS["min_cores"]) + 4,
            ram_gb=int(SPECS["min_ram_gb"]) + 32,
            disk_gb=int(SPECS["min_disk_gb"]) + 1024,
            quoted_price=3100.0,  # USD
            includes_warranty=True,
            includes_tax=False,
            includes_shipping=False,
            warranty_cost=None,
            tax_amount=None,
            shipping_cost=None,
            warranty_years=3.0,
            currency="USD",
        )
        pricing = PricingCalculatorResult(has_missing_inputs=False)
        
        compliance = _compute_compliance(
            fields,
            pricing,
            rate_local_per_usd=USD_RATE,
            includes_tax=None,
            includes_shipping=None,
            includes_warranty=None,
        )
        # 3100 USD > 2900 USD limit
        assert compliance.price_pass is False
