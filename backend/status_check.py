from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

from googleapiclient.errors import HttpError

from .common.google_drive import get_drive_service
from .common.google_sheets import get_sheets_service


@dataclass
class CheckResult:
    ok: bool
    detail: str


class StatusCheckService:
    def run(self) -> dict[str, Any]:
        checks = {
            "session_secret": self._check_session_secret(),
            "oauth_client": self._check_oauth_client(),
            "service_account": self._check_service_account(),
            "onboarding_folder_config": self._check_onboarding_folder_config(),
            "drive_access": self._check_drive_access(),
            "waitlist_sheet_access": self._check_waitlist_sheet_access(),
        }

        all_ok = all(item.ok for item in checks.values())
        return {
            "ok": all_ok,
            "checks": {
                key: {"ok": value.ok, "detail": value.detail}
                for key, value in checks.items()
            },
        }

    def _check_session_secret(self) -> CheckResult:
        value = os.getenv("SESSION_SECRET", "").strip()
        if not value:
            return CheckResult(False, "SESSION_SECRET is not set")
        if value == "dev-session-secret":
            return CheckResult(False, "SESSION_SECRET is still set to development default")
        return CheckResult(True, "SESSION_SECRET configured")

    def _check_oauth_client(self) -> CheckResult:
        client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
        client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            return CheckResult(False, "GOOGLE_OAUTH_CLIENT_ID/GOOGLE_OAUTH_CLIENT_SECRET must be set")
        return CheckResult(True, "OAuth client configuration present")

    def _check_service_account(self) -> CheckResult:
        sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        app_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        if not sa_json and not app_creds:
            return CheckResult(False, "Neither GOOGLE_SERVICE_ACCOUNT_JSON nor GOOGLE_APPLICATION_CREDENTIALS is set")
        return CheckResult(True, "Service account credentials configured")

    def _check_onboarding_folder_config(self) -> CheckResult:
        folder_ref = os.getenv("GOOGLE_DRIVE_ONBOARDING_FOLDER_ID", "").strip()
        folder_id = self._extract_drive_folder_id(folder_ref)
        if not folder_ref or not folder_id:
            return CheckResult(False, "GOOGLE_DRIVE_ONBOARDING_FOLDER_ID is missing or invalid")
        return CheckResult(True, "Onboarding folder reference configured")

    def _check_drive_access(self) -> CheckResult:
        folder_ref = os.getenv("GOOGLE_DRIVE_ONBOARDING_FOLDER_ID", "").strip()
        folder_id = self._extract_drive_folder_id(folder_ref)
        if not folder_id:
            return CheckResult(False, "Cannot test Drive access: onboarding folder id is missing")

        try:
            drive = get_drive_service()
            drive.files().get(fileId=folder_id, fields="id,name,driveId", supportsAllDrives=True).execute()
            return CheckResult(True, "Drive folder is reachable")
        except HttpError as exc:
            return CheckResult(False, f"Drive access failed: {self._summarize_http_error(exc)}")
        except Exception as exc:  # pragma: no cover - defensive fallback
            return CheckResult(False, f"Drive access failed: {exc}")

    def _check_waitlist_sheet_access(self) -> CheckResult:
        spreadsheet_id = os.getenv("GOOGLE_WAITLIST_SPREADSHEET_ID", "").strip()
        if not spreadsheet_id:
            return CheckResult(False, "GOOGLE_WAITLIST_SPREADSHEET_ID is not set")

        try:
            sheets = get_sheets_service()
            sheets.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range="Sheet1!A1:C1",
            ).execute()
            return CheckResult(True, "Waitlist sheet is reachable")
        except HttpError as exc:
            return CheckResult(False, f"Waitlist sheet access failed: {self._summarize_http_error(exc)}")
        except Exception as exc:  # pragma: no cover - defensive fallback
            return CheckResult(False, f"Waitlist sheet access failed: {exc}")

    @staticmethod
    def _extract_drive_folder_id(folder_ref: str) -> str:
        value = folder_ref.strip()
        if not value:
            return ""

        # Accept plain IDs and common Drive URL shapes.
        if "/" not in value and "?" not in value:
            return value

        parsed = urlparse(value)
        if not parsed.scheme:
            return value

        query_id = parse_qs(parsed.query).get("id", [""])[0]
        if query_id:
            return query_id

        parts = [part for part in parsed.path.split("/") if part]
        if "folders" in parts:
            idx = parts.index("folders")
            if idx + 1 < len(parts):
                return parts[idx + 1]

        return ""

    @staticmethod
    def _summarize_http_error(exc: HttpError) -> str:
        status = getattr(getattr(exc, "resp", None), "status", "unknown")
        return f"HTTP {status}: {exc}"
