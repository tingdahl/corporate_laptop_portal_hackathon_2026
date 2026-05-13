#!/usr/bin/env python3
"""Test Google Drive API access with service account"""

import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load credentials
creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/home/kristofer.tingdahl@canonical.com/Development/information-systems-corporate-laptops/staff_portal/service-account.json")
print(f"Loading credentials from: {creds_path}")

credentials = service_account.Credentials.from_service_account_file(
    creds_path,
    scopes=["https://www.googleapis.com/auth/drive"]
)

print(f"Service account email: {credentials.service_account_email}")

# Build Drive service
service = build("drive", "v3", credentials=credentials)

# Test folder IDs
pdf_folder_id = "1D-UrlsJIxUXkQxVmeJ3B3SU5JHmxm0C"
inputs_folder_id = "12y-lzgfp0IlzQyqbiBDS5_OqRs9XztJT"

print(f"\n--- Testing PDF folder: {pdf_folder_id} ---")
try:
    result = service.files().get(fileId=pdf_folder_id, fields="id,name,mimeType,capabilities").execute()
    print(f"✓ SUCCESS: Folder accessible")
    print(f"  Name: {result.get('name')}")
    print(f"  Type: {result.get('mimeType')}")
    print(f"  Capabilities: {result.get('capabilities')}")
except Exception as e:
    print(f"✗ FAILED: {e}")

print(f"\n--- Testing Inputs folder: {inputs_folder_id} ---")
try:
    result = service.files().get(fileId=inputs_folder_id, fields="id,name,mimeType,capabilities").execute()
    print(f"✓ SUCCESS: Folder accessible")
    print(f"  Name: {result.get('name')}")
    print(f"  Type: {result.get('mimeType')}")
    print(f"  Capabilities: {result.get('capabilities')}")
except Exception as e:
    print(f"✗ FAILED: {e}")

print(f"\n--- Checking Drive API availability ---")
try:
    # Try to list some files to see if the API is working at all
    results = service.files().list(pageSize=1, fields="files(id, name)").execute()
    files = results.get('files', [])
    print(f"✓ Drive API is working (found {len(files)} files in test query)")
except Exception as e:
    print(f"✗ Drive API error: {e}")
