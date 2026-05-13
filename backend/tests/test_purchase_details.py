from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.purchases.purchase_details import (
    ExpenseTransaction,
    PurchaseSpreadsheetLoader,
    _extract_spreadsheet_id,
    calculate_purchase_details,
    parse_transaction_amount,
)


class _FakeSheetValuesGet:
    def __init__(self, payload: dict):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakeSheetValues:
    def __init__(self, payload: dict):
        self._payload = payload

    def get(self, *, spreadsheetId: str, range: str):
        assert spreadsheetId
        assert range == "Summary!A:I"
        return _FakeSheetValuesGet(self._payload)


class _FakeSpreadsheets:
    def __init__(self, payload: dict):
        self._payload = payload

    def values(self):
        return _FakeSheetValues(self._payload)


class _FakeSheetsService:
    def __init__(self, payload: dict):
        self._payload = payload

    def spreadsheets(self):
        return _FakeSpreadsheets(self._payload)


def test_parse_transaction_amount_supports_currency_symbols_and_signs() -> None:
    assert parse_transaction_amount("$2,598") == Decimal("2598")
    assert parse_transaction_amount("-$113") == Decimal("-113")
    assert parse_transaction_amount("+132") == Decimal("132")


def test_grouping_uses_14_day_window_from_first_transaction() -> None:
    transactions = [
        ExpenseTransaction("user@canonical.com", "$1000", "USD", "2026-01-01"),
        ExpenseTransaction("user@canonical.com", "$200", "USD", "2026-01-15"),
        ExpenseTransaction("user@canonical.com", "$300", "USD", "2026-01-16"),
    ]

    result = calculate_purchase_details(transactions, as_of_date=date(2026, 1, 20))

    assert len(result) == 2
    assert result[0].net_amount_local == Decimal("1200.00")
    assert len(result[0].transactions) == 2
    assert result[1].net_amount_local == Decimal("300.00")
    assert len(result[1].transactions) == 1


def test_negative_amounts_reduce_group_net() -> None:
    transactions = [
        ExpenseTransaction("user@canonical.com", "$2000", "USD", "2026-02-01"),
        ExpenseTransaction("user@canonical.com", "-$100", "USD", "2026-02-03"),
    ]

    result = calculate_purchase_details(transactions, as_of_date=date(2026, 2, 10))

    assert len(result) == 1
    assert result[0].net_amount_local == Decimal("1900.00")


def test_non_positive_group_is_marked_as_anomaly() -> None:
    transactions = [
        ExpenseTransaction("user@canonical.com", "$100", "USD", "2026-03-01"),
        ExpenseTransaction("user@canonical.com", "-$250", "USD", "2026-03-02"),
    ]

    result = calculate_purchase_details(transactions, as_of_date=date(2026, 3, 5))

    assert len(result) == 1
    assert result[0].net_amount_local == Decimal("-150.00")
    assert "non_positive_net_amount" in result[0].anomalies
    assert result[0].current_depreciated_value_local == Decimal("0.00")


def test_high_value_group_is_marked_as_bundle_outlier() -> None:
    transactions = [
        ExpenseTransaction("user@canonical.com", "$5000", "USD", "2026-04-01"),
    ]

    result = calculate_purchase_details(
        transactions,
        as_of_date=date(2026, 4, 2),
        max_laptop_price_usd=2900,
    )

    assert len(result) == 1
    assert "potential_multi_item_bundle" in result[0].anomalies


def test_depreciation_is_linear_over_three_years() -> None:
    transactions = [
        ExpenseTransaction("user@canonical.com", "$1095", "USD", "2026-01-01"),
    ]

    # writeoff_months=36 → 36 * 30.4375 = 1095.75 depreciation days
    after_one_year = calculate_purchase_details(
        transactions, as_of_date=date(2027, 1, 1), writeoff_months=36
    )[0]
    after_three_years = calculate_purchase_details(
        transactions, as_of_date=date(2029, 1, 1), writeoff_months=36
    )[0]

    # elapsed 365 days / 1095.75 ≈ 0.3331 → remaining ≈ 0.6669 → 1095 * 0.6669 ≈ 730.25
    assert after_one_year.current_depreciated_value_local == Decimal("730.25")
    assert after_three_years.current_depreciated_value_local == Decimal("0.00")


def test_uses_exchange_rate_to_calculate_usd_totals() -> None:
    transactions = [
        ExpenseTransaction("user@canonical.com", "2600", "EUR", "2026-05-01"),
    ]

    result = calculate_purchase_details(
        transactions,
        as_of_date=date(2026, 5, 2),
        exchange_rates_local_per_usd={"EUR": 0.85},
    )[0]

    assert result.net_amount_local == Decimal("2600.00")
    assert result.net_amount_usd == Decimal("3058.82")
    assert result.exchange_rate_local_per_usd == 0.85


def test_mixed_currency_group_is_marked_as_mixed_and_has_no_usd_total() -> None:
    transactions = [
        ExpenseTransaction("user@canonical.com", "100", "USD", "2026-06-01"),
        ExpenseTransaction("user@canonical.com", "100", "EUR", "2026-06-03"),
    ]

    result = calculate_purchase_details(transactions, as_of_date=date(2026, 6, 10))[0]

    assert result.currency == "MIXED"
    assert result.net_amount_usd is None


def test_groups_are_isolated_per_employee() -> None:
    transactions = [
        ExpenseTransaction("a@canonical.com", "100", "USD", "2026-07-01"),
        ExpenseTransaction("b@canonical.com", "200", "USD", "2026-07-01"),
    ]

    result = calculate_purchase_details(transactions, as_of_date=date(2026, 7, 2))

    assert len(result) == 2
    assert [item.employee_email for item in result] == ["a@canonical.com", "b@canonical.com"]


def test_parse_transaction_amount_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        parse_transaction_amount("abc")


def test_extract_spreadsheet_id_from_url() -> None:
    ref = "https://docs.google.com/spreadsheets/d/13QBJeIg342Bgtgv1J-0-U47JXhp5CWH2NJJrzTqOIK0/edit?gid=499879560"
    assert _extract_spreadsheet_id(ref) == "13QBJeIg342Bgtgv1J-0-U47JXhp5CWH2NJJrzTqOIK0"


def test_loader_reads_summary_rows_as_transactions() -> None:
    payload = {
        "values": [
            ["Employee e-mail", "Date", "Currency", "Amount", "Process", "Reference", "Comment"],
            ["user@canonical.com", "2026-01-01", "USD", "$1000", "P", "R1", "Laptop"],
            ["", "2026-01-02", "USD", "$50", "P", "R2", "Missing email"],
        ]
    }

    loader = PurchaseSpreadsheetLoader(
        sheets_service=_FakeSheetsService(payload),
        spreadsheet_ref="13QBJeIg342Bgtgv1J-0-U47JXhp5CWH2NJJrzTqOIK0",
    )

    transactions = loader.load_transactions()
    assert len(transactions) == 1
    assert transactions[0].email == "user@canonical.com"
    assert transactions[0].date == "2026-01-01"
    assert transactions[0].currency == "USD"
    assert transactions[0].amount == "$1000"


def test_loader_returns_purchases_for_named_user() -> None:
    payload = {
        "values": [
            ["Employee e-mail", "Date", "Currency", "Amount", "Process", "Reference", "Comment"],
            ["user@canonical.com", "2026-01-01", "USD", "$1200", "P", "R1", "Laptop"],
            ["user@canonical.com", "2026-01-03", "USD", "-$200", "P", "R2", "Refund"],
            ["other@canonical.com", "2026-01-01", "USD", "$999", "P", "R3", "Other"],
        ]
    }

    loader = PurchaseSpreadsheetLoader(
        sheets_service=_FakeSheetsService(payload),
        spreadsheet_ref="13QBJeIg342Bgtgv1J-0-U47JXhp5CWH2NJJrzTqOIK0",
    )

    purchases = loader.purchases_for_user("user@canonical.com", as_of_date=date(2026, 1, 10))
    assert len(purchases) == 1
    assert purchases[0].employee_email == "user@canonical.com"
    assert purchases[0].net_amount_local == Decimal("1000.00")
