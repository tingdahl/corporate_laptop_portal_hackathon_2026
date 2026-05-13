from __future__ import annotations

import json
import os

import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build


SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _load_google_credentials():
    service_account_ref = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if service_account_ref:
        if service_account_ref.startswith("{"):
            info = json.loads(service_account_ref)
            return service_account.Credentials.from_service_account_info(info, scopes=SHEETS_SCOPES)
        return service_account.Credentials.from_service_account_file(service_account_ref, scopes=SHEETS_SCOPES)

    credentials, _ = google.auth.default(scopes=SHEETS_SCOPES)
    return credentials


def get_sheets_service():
    credentials = _load_google_credentials()
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)