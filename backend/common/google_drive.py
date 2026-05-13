from __future__ import annotations

import io

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


def get_drive_service():
    # Uses GOOGLE_APPLICATION_CREDENTIALS service account credentials.
    return build("drive", "v3", cache_discovery=False)


def ensure_user_folder(service, root_folder_id: str, user_email: str) -> str:
    escaped_email = user_email.replace("'", "\\'")
    query = (
        f"name = '{escaped_email}' and "
        f"'{root_folder_id}' in parents and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    existing = service.files().list(q=query, fields="files(id,name)", pageSize=1).execute()
    files = existing.get("files", [])
    if files:
        return files[0]["id"]

    created = (
        service.files()
        .create(
            body={
                "name": user_email,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [root_folder_id],
            },
            fields="id",
        )
        .execute()
    )
    return created["id"]


def verify_folder_access(service, folder_id: str) -> bool:
    """
    Verify that the service account can access a folder.
    Returns True if accessible, False otherwise.
    """
    try:
        print(f"DEBUG google_drive: Checking access to folder {folder_id}")
        result = service.files().get(fileId=folder_id, fields="id,name").execute()
        print(f"DEBUG google_drive: Folder accessible: {result.get('name')}")
        return True
    except Exception as e:
        print(f"DEBUG google_drive: Folder {folder_id} NOT accessible: {str(e)}")
        return False


def upload_file(
    service,
    folder_id: str,
    filename: str,
    content: bytes,
    mime_type: str = "application/octet-stream"
) -> tuple[str, str]:
    """
    Upload a file to Google Drive.
    
    Returns:
        Tuple of (file_id, web_view_link)
    """
    media = MediaIoBaseUpload(
        io.BytesIO(content),
        mimetype=mime_type,
        resumable=True
    )
    
    file_metadata = {
        "name": filename,
        "parents": [folder_id]
    }
    
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id,webViewLink"
    ).execute()
    
    return uploaded_file["id"], uploaded_file["webViewLink"]