from __future__ import annotations

from datetime import date
import os

from fastapi import APIRouter, Cookie, Query, HTTPException

from ..auth.routes import current_user_email
from ..contracts.purchase_details import (
    EmployeesPurchaseListResponse,
    EmployeePurchaseRowResponse,
    PurchaseEligibilityResponse,
    ParsedTransactionResponse,
    PurchaseDetailsResponse,
    PurchaseSummaryResponse,
)
from .purchase_details import PurchaseSpreadsheetLoader, calculate_purchase_details

purchase_router = APIRouter(prefix="/purchase_details", tags=["purchases"])


def _get_admin_users() -> set[str]:
    """Parse ADMIN_USERS env var as comma-separated list of emails."""
    admin_str = os.getenv("ADMIN_USERS", "")
    if not admin_str.strip():
        return set()
    return {email.strip().lower() for email in admin_str.split(",") if email.strip()}


def _require_admin(user_email: str) -> None:
    """Raise 403 if user is not in ADMIN_USERS list."""
    admin_users = _get_admin_users()
    if user_email.lower() not in admin_users:
        raise HTTPException(status_code=403, detail="Access denied: admin access required")


def _to_purchase_summary_response(summary) -> PurchaseSummaryResponse:
    return PurchaseSummaryResponse(
        purchase_date=summary.purchase_date,
        window_end_date=summary.window_end_date,
        next_refresh_date=summary.next_refresh_date,
        currency=summary.currency,
        net_amount_local=float(summary.net_amount_local),
        net_amount_usd=float(summary.net_amount_usd) if summary.net_amount_usd is not None else None,
        exchange_rate_local_per_usd=summary.exchange_rate_local_per_usd,
        current_depreciated_value_local=float(summary.current_depreciated_value_local),
        current_depreciated_value_usd=float(summary.current_depreciated_value_usd) if summary.current_depreciated_value_usd is not None else None,
        anomalies=list(summary.anomalies),
        transactions=[
            ParsedTransactionResponse(
                email=t.email,
                amount_signed=float(t.amount_signed),
                currency=t.currency,
                date=t.date,
            )
            for t in summary.transactions
        ],
    )


@purchase_router.get("", response_model=PurchaseDetailsResponse)
def get_purchase_details(
    staff_portal_session: str | None = Cookie(default=None),
) -> PurchaseDetailsResponse:
    user_email = current_user_email(staff_portal_session)
    loader = PurchaseSpreadsheetLoader()
    summaries = loader.purchases_for_user(user_email)

    purchases = [_to_purchase_summary_response(s) for s in summaries]

    return PurchaseDetailsResponse(employee_email=user_email, purchases=purchases)


@purchase_router.get("/employees", response_model=EmployeesPurchaseListResponse)
def get_employees_purchase_list(
    staff_portal_session: str | None = Cookie(default=None),
) -> EmployeesPurchaseListResponse:
    user_email = current_user_email(staff_portal_session)
    _require_admin(user_email)
    loader = PurchaseSpreadsheetLoader()
    summaries = calculate_purchase_details(loader.load_transactions())

    latest_by_employee: dict[str, date] = {}
    for summary in summaries:
        current = latest_by_employee.get(summary.employee_email)
        if current is None or summary.purchase_date > current:
            latest_by_employee[summary.employee_email] = summary.purchase_date

    employees = [
        EmployeePurchaseRowResponse(employee_email=email, latest_purchase_date=latest_date)
        for email, latest_date in latest_by_employee.items()
    ]
    employees.sort(key=lambda item: item.latest_purchase_date, reverse=True)

    return EmployeesPurchaseListResponse(
        total_employees=len(employees),
        employees=employees,
    )


@purchase_router.get("/employee", response_model=PurchaseDetailsResponse)
def get_employee_purchase_details(
    email: str = Query(min_length=3),
    staff_portal_session: str | None = Cookie(default=None),
) -> PurchaseDetailsResponse:
    user_email = current_user_email(staff_portal_session)
    target_email = email.strip().lower()
    
    # Allow viewing own details, or require admin for others
    if user_email.lower() != target_email:
        _require_admin(user_email)
    loader = PurchaseSpreadsheetLoader()
    summaries = loader.purchases_for_user(target_email)
    purchases = [_to_purchase_summary_response(s) for s in summaries]

    return PurchaseDetailsResponse(employee_email=target_email, purchases=purchases)


@purchase_router.get("/eligibility", response_model=PurchaseEligibilityResponse)
def get_purchase_eligibility(
    staff_portal_session: str | None = Cookie(default=None),
) -> PurchaseEligibilityResponse:
    user_email = current_user_email(staff_portal_session)
    loader = PurchaseSpreadsheetLoader()
    summaries = loader.purchases_for_user(user_email)

    writeoff_months = int(os.getenv("WRITEOFF_MONTHS", "36"))

    if not summaries:
        return PurchaseEligibilityResponse(
            employee_email=user_email,
            eligible_for_new_laptop=True,
            latest_purchase_date=None,
            next_planned_laptop_refresh=None,
            writeoff_months=writeoff_months,
        )

    latest = max(summaries, key=lambda item: item.purchase_date)
    today = date.today()
    eligible = latest.next_refresh_date <= today

    return PurchaseEligibilityResponse(
        employee_email=user_email,
        eligible_for_new_laptop=eligible,
        latest_purchase_date=latest.purchase_date,
        next_planned_laptop_refresh=latest.next_refresh_date,
        writeoff_months=writeoff_months,
    )
