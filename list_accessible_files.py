#!/usr/bin/env python3
"""List all files/folders accessible to the service account"""

import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load credentials
creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/home/kristofer.tingdahl@canonical.com/Development/information-systems-corporate-laptops/staff_portal/service-account.json")
credentials = service_account.Credentials.from_service_account_file(
    creds_path,
    scopes=["https://www.googleapis.com/auth/drive"]
)

# Build Drive service
service = build("drive", "v3", credentials=credentials)

print("Files and folders shared with service account:")
print("=" * 60)

try:
    # List all files the service account can see
    results = service.files().list(
        pageSize=50,
        fields="files(id, name, mimeType, owners)"
    ).execute()
    
    files = results.get('files', [])
    
    if not files:
        print("No files found. This means NO folders/files have been shared with the service account.")
    else:
        print(f"Found {len(files)} files/folders:\n")
        for item in files:
            item_type = "📁 Folder" if item['mimeType'] == 'application/vnd.google-apps.folder' else "📄 File"
            owners = ", ".join([owner.get('emailAddress', 'unknown') for owner in item.get('owners', [])])
            print(f"{item_type}: {item['name']}")
            print(f"  ID: {item['id']}")
            print(f"  Owner: {owners}")
            print()
            
except Exception as e:
    print(f"Error listing files: {e}")
