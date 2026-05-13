from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CsvLifecycleStatus(str, Enum):
    GENERATED = "Generated"
    SUBMITTED = "Submitted"
    PROCESSED = "Processed"


class WaitingListMissingField(str, Enum):
    PHONE = "phone"
    ADDRESS = "address"


class EligibleEmployeeRecord(ContractModel):
    email: str = Field(description="Canonical user email.")
    first_name: str | None = None
    last_name: str | None = None
    first_day_of_employment_utc: date
    last_laptop_purchase_date_utc: date | None = None
    eligibility_date_utc: date
    waiting_since_utc: date | None = Field(
        default=None,
        description="Date the employee was added to the waitlist, when applicable.",
    )
    waiting_list: bool = False
    waiting_list_missing_fields: list[WaitingListMissingField] = Field(default_factory=list)


class EligibleListReason(str, Enum):
    LAPTOP_REFRESH_AFTER_3_YEARS = "Laptop refresh after 3 years"
    FROM_WAIT_LIST = "From wait list"
    FROM_STARTERS = "From starters"


class EligibleListRow(ContractModel):
    email: str
    reason: EligibleListReason
    reference_date_utc: date | None = Field(
        default=None,
        description="For starters this is the start date; for refreshers this is the 3-year eligibility date.",
    )


class EligibleEmployeesCounts(ContractModel):
    eligible_total: int = Field(ge=0)
    waiting_list_total: int = Field(ge=0)
    excluded_first_added_today_total: int = Field(ge=0)


class GetEligibleResponse(ContractModel):
    generated_at_utc: datetime
    eligibility_cutoff_utc_date: date = Field(
        description="Employees first added after this UTC date are excluded from this run."
    )
    counts: EligibleEmployeesCounts
    eligible_employees: list[EligibleEmployeeRecord]
    waiting_list_employees: list[EligibleEmployeeRecord]
    display_rows: list[EligibleListRow] = Field(
        default_factory=list,
        description="Three-column onboarding list: e-mail, reason, and optional reference date.",
    )


class EligibleCsvRowStatus(str, Enum):
    INCLUDED = "included"
    WAITING_LIST = "waiting_list"
    EXCLUDED = "excluded"


class EligibleCsvRow(ContractModel):
    row_number: int = Field(ge=1)
    email: str
    first_name: str | None = None
    last_name: str | None = None
    row_status: EligibleCsvRowStatus
    exclusion_reason: str | None = None


class CsvFileSummary(ContractModel):
    id: str = Field(description="Stable identifier used by /api/csvs/{id}/status.")
    drive_file_id: str
    filename: str = Field(description="Must match expensify-YYYY-MM-DD-<Status>.csv.")
    download_link: str | None = Field(
        default=None,
        description="Direct file download link used for filename click action in the onboarding CSV list.",
    )
    drive_web_view_link: str | None = None
    status: CsvLifecycleStatus
    status_encoded_in_filename: bool
    created_at_utc: datetime
    updated_at_utc: datetime
    row_count: int = Field(ge=0)
    employee_count: int = Field(ge=0)


class GenerateEligibleCsvRequest(ContractModel):
    dry_run: bool = Field(
        default=False,
        description="If true, evaluate eligibility and rows without creating/uploading a file.",
    )
    include_recovered_waiting_list_employees: bool = Field(
        default=True,
        description="If true, remove waiting list entries now present in generated CSV.",
    )


class GenerateEligibleCsvCounts(ContractModel):
    included_total: int = Field(ge=0)
    waiting_list_total: int = Field(ge=0)
    recovered_from_waiting_list_total: int = Field(ge=0)


class GenerateEligibleCsvResponse(ContractModel):
    generated_at_utc: datetime
    eligibility_cutoff_utc_date: date
    csv: CsvFileSummary
    counts: GenerateEligibleCsvCounts
    rows: list[EligibleCsvRow]


class ListCsvFilesResponse(ContractModel):
    retrieved_at_utc: datetime
    total: int = Field(ge=0)
    csv_files: list[CsvFileSummary]


class InstructionEmailAction(str, Enum):
    NOT_REQUESTED = "not_requested"
    QUEUED = "queued"
    SENT = "sent"
    SKIPPED = "skipped"
    DISABLED = "disabled"


class ChangeCsvStatusRequest(ContractModel):
    target_status: CsvLifecycleStatus
    confirm: Literal[True] = Field(
        description="Explicit confirmation required before any lifecycle status update."
    )
    reason: str | None = None
    send_instruction_emails_on_processed: bool = Field(
        default=False,
        description="If target status is Processed, request instruction email dispatch.",
    )


class CsvStatusTransition(ContractModel):
    previous_status: CsvLifecycleStatus
    current_status: CsvLifecycleStatus
    changed_at_utc: datetime
    status_change_was_reversal: bool
    instruction_email_action: InstructionEmailAction


class ChangeCsvStatusResponse(ContractModel):
    csv: CsvFileSummary
    transition: CsvStatusTransition
