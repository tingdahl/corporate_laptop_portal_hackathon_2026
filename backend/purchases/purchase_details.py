from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import os
import re
from typing import Iterable
from urllib.parse import parse_qs, urlparse

from ..common.google_sheets import get_sheets_service


_AMOUNT_CHARS_PATTERN = re.compile(r"[^0-9.,\-+]")
_MIXED_CURRENCY = "MIXED"
_DEFAULT_WRITEOFF_MONTHS = 36
_DEFAULT_PURCHASE_RANGE = "Summary!A:I"


def _configured_writeoff_months() -> int:
    return int(os.getenv("WRITEOFF_MONTHS", str(_DEFAULT_WRITEOFF_MONTHS)))


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.strip().lower())


def _extract_spreadsheet_id(spreadsheet_ref: str) -> str:
    value = spreadsheet_ref.strip()
    if not value:
        raise ValueError("GOOGLE_DRIVE_PURCHASE_SPREADSHEET is not set")

    if "/" not in value and "?" not in value:
        return value

    parsed = urlparse(value)
    if not parsed.scheme:
        return value

    query_id = parse_qs(parsed.query).get("id", [""])[0]
    if query_id:
        return query_id

    parts = [part for part in parsed.path.split("/") if part]
    if "d" in parts:
        idx = parts.index("d")
        if idx + 1 < len(parts):
            return parts[idx + 1]

    raise ValueError("Invalid purchase spreadsheet reference")


def _configured_max_laptop_price_usd() -> float:
    return float(os.getenv("MAX_PRICE_USD", "2900"))


def _add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    import calendar
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@dataclass(frozen=True)
class ExpenseTransaction:
    email: str
    amount: str | int | float | Decimal
    currency: str
    date: str | date | datetime


@dataclass(frozen=True)
class ParsedExpenseTransaction:
    email: str
    amount_signed: Decimal
    currency: str
    date: date


@dataclass(frozen=True)
class PurchaseSummary:
    employee_email: str
    purchase_date: date
    window_end_date: date
    next_refresh_date: date
    currency: str
    net_amount_local: Decimal
    net_amount_usd: Decimal | None
    exchange_rate_local_per_usd: float | None
    current_depreciated_value_local: Decimal
    current_depreciated_value_usd: Decimal | None
    anomalies: tuple[str, ...]
    transactions: tuple[ParsedExpenseTransaction, ...]


class PurchaseSpreadsheetLoader:
    def __init__(
        self,
        *,
        sheets_service=None,
        spreadsheet_ref: str | None = None,
        summary_range: str = _DEFAULT_PURCHASE_RANGE,
    ) -> None:
        self._sheets_service = sheets_service or get_sheets_service()
        self._spreadsheet_ref = spreadsheet_ref or os.getenv("GOOGLE_DRIVE_PURCHASE_SPREADSHEET", "")
        self._summary_range = summary_range

    def load_transactions(self) -> list[ExpenseTransaction]:
        spreadsheet_id = _extract_spreadsheet_id(self._spreadsheet_ref)
        response = self._sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=self._summary_range,
        ).execute()

        values = response.get("values", [])
        if not values:
            return []

        header = values[0]
        header_map = {
            _normalize_header(name): idx
            for idx, name in enumerate(header)
            if name and name.strip()
        }

        def col_index(*aliases: str) -> int:
            for alias in aliases:
                idx = header_map.get(_normalize_header(alias))
                if idx is not None:
                    return idx
            raise ValueError(f"Required column missing in purchase sheet header: {aliases[0]}")

        email_idx = col_index("Employee e-mail", "Employee email", "E-mail", "Email")
        date_idx = col_index("Date")
        currency_idx = col_index("Currency")
        amount_idx = col_index("Amount")

        transactions: list[ExpenseTransaction] = []
        for row in values[1:]:
            email = row[email_idx].strip() if email_idx < len(row) else ""
            tx_date = row[date_idx].strip() if date_idx < len(row) else ""
            currency = row[currency_idx].strip() if currency_idx < len(row) else ""
            amount = row[amount_idx].strip() if amount_idx < len(row) else ""
            if not email or not tx_date or not currency or not amount:
                continue

            transactions.append(
                ExpenseTransaction(
                    email=email,
                    date=tx_date,
                    currency=currency,
                    amount=amount,
                )
            )

        return transactions

    def purchases_for_user(
        self,
        email: str,
        *,
        as_of_date: date | None = None,
        exchange_rates_local_per_usd: dict[str, float] | None = None,
        max_laptop_price_usd: float | None = None,
        writeoff_months: int | None = None,
    ) -> list[PurchaseSummary]:
        target_email = email.strip().lower()
        if not target_email:
            return []

        user_transactions = [
            tx for tx in self.load_transactions() if tx.email.strip().lower() == target_email
        ]

        return calculate_purchase_details(
            user_transactions,
            as_of_date=as_of_date,
            exchange_rates_local_per_usd=exchange_rates_local_per_usd,
            max_laptop_price_usd=max_laptop_price_usd,
            writeoff_months=writeoff_months,
        )


def parse_transaction_amount(value: str | int | float | Decimal) -> Decimal:
    """
    Parse signed amount values such as "$2,598", "$132", and "-$113".
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    raw = value.strip()
    if not raw:
        raise ValueError("Amount cannot be empty")

    cleaned = _AMOUNT_CHARS_PATTERN.sub("", raw)
    if not cleaned:
        raise ValueError(f"Invalid amount: {value!r}")

    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", "")

    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid amount: {value!r}") from exc


def _parse_transaction_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _normalize_transaction(tx: ExpenseTransaction) -> ParsedExpenseTransaction:
    return ParsedExpenseTransaction(
        email=tx.email.strip().lower(),
        amount_signed=parse_transaction_amount(tx.amount),
        currency=tx.currency.strip().upper(),
        date=_parse_transaction_date(tx.date),
    )


def calculate_purchase_details(
    transactions: Iterable[ExpenseTransaction],
    *,
    as_of_date: date | None = None,
    exchange_rates_local_per_usd: dict[str, float] | None = None,
    max_laptop_price_usd: float | None = None,
    writeoff_months: int | None = None,
) -> list[PurchaseSummary]:
    """
    Distill laptop purchases from raw expense transactions using section 4.3 rules.

    Grouping rules:
    - primary key is employee email
    - per employee, sort by date ascending
    - start group at first unassigned transaction
    - include later transactions within 14 calendar days from first transaction
    """
    normalized = [_normalize_transaction(tx) for tx in transactions]
    by_employee: dict[str, list[ParsedExpenseTransaction]] = {}
    for tx in normalized:
        by_employee.setdefault(tx.email, []).append(tx)

    as_of = as_of_date or datetime.now(timezone.utc).date()
    rates = {k.upper(): v for k, v in (exchange_rates_local_per_usd or {}).items()}
    max_price = max_laptop_price_usd if max_laptop_price_usd is not None else _configured_max_laptop_price_usd()
    wo_months = writeoff_months if writeoff_months is not None else _configured_writeoff_months()
    depreciation_days = wo_months * 30.4375

    summaries: list[PurchaseSummary] = []

    for email, employee_transactions in by_employee.items():
        employee_transactions.sort(key=lambda item: item.date)
        index = 0

        while index < len(employee_transactions):
            first = employee_transactions[index]
            window_end = first.date.fromordinal(first.date.toordinal() + 14)

            grouped: list[ParsedExpenseTransaction] = [first]
            index += 1
            while index < len(employee_transactions) and employee_transactions[index].date <= window_end:
                grouped.append(employee_transactions[index])
                index += 1

            net_local = sum((tx.amount_signed for tx in grouped), Decimal("0"))
            currency_values = {tx.currency for tx in grouped}

            currency = next(iter(currency_values)) if len(currency_values) == 1 else _MIXED_CURRENCY
            exchange_rate = rates.get(currency)
            net_usd = None
            if exchange_rate:
                net_usd = (net_local / Decimal(str(exchange_rate))).quantize(Decimal("0.01"))
            elif currency == "USD":
                exchange_rate = 1.0
                net_usd = net_local.quantize(Decimal("0.01"))

            anomalies: list[str] = []
            if net_local <= 0:
                anomalies.append("non_positive_net_amount")

            outlier_amount_usd: Decimal | None = net_usd
            if outlier_amount_usd is None and currency == "USD":
                outlier_amount_usd = net_local

            if outlier_amount_usd is not None and outlier_amount_usd > Decimal(str(max_price * 1.7)):
                anomalies.append("potential_multi_item_bundle")

            elapsed_days = max(0, (as_of - first.date).days)
            remaining_ratio = max(0.0, 1.0 - (elapsed_days / depreciation_days))
            next_refresh_date = _add_months(first.date, wo_months)

            depreciated_local_raw = net_local * Decimal(str(remaining_ratio))
            depreciated_local = max(Decimal("0"), depreciated_local_raw).quantize(Decimal("0.01"))

            depreciated_usd = None
            if net_usd is not None:
                depreciated_usd_raw = net_usd * Decimal(str(remaining_ratio))
                depreciated_usd = max(Decimal("0"), depreciated_usd_raw).quantize(Decimal("0.01"))

            summaries.append(
                PurchaseSummary(
                    employee_email=email,
                    purchase_date=first.date,
                    window_end_date=window_end,
                    next_refresh_date=next_refresh_date,
                    currency=currency,
                    net_amount_local=net_local.quantize(Decimal("0.01")),
                    net_amount_usd=net_usd,
                    exchange_rate_local_per_usd=exchange_rate,
                    current_depreciated_value_local=depreciated_local,
                    current_depreciated_value_usd=depreciated_usd,
                    anomalies=tuple(anomalies),
                    transactions=tuple(grouped),
                )
            )

    summaries.sort(key=lambda item: (item.employee_email, item.purchase_date))
    return summaries
