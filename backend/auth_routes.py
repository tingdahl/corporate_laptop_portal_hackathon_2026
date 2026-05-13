from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Cookie, HTTPException, Query, Response
from google.auth.transport.requests import Request as GoogleTokenRequest
from google.oauth2 import id_token
from itsdangerous import BadSignature, URLSafeSerializer

from contracts import (
    AuthCallbackResponse,
    ConfigResponse,
    GoogleAuthRequest,
    GoogleAuthResponse,
    LogoutResponse,
    MeResponse,
)


auth_router = APIRouter(tags=["auth"])

GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
ALLOWED_EMAIL_DOMAIN = "canonical.com"


def _sessions() -> URLSafeSerializer:
    return URLSafeSerializer(os.getenv("SESSION_SECRET", "dev-session-secret"), salt="staff-portal")


def session_cookie() -> str:
    return "staff_portal_session"


def current_user_email(session_token: str | None = None) -> str:
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = _sessions().loads(session_token)
    except BadSignature as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc
    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid session payload")
    return str(email)


def _require_canonical_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized.endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
        raise HTTPException(status_code=403, detail="Only canonical.com accounts are authorized")
    return normalized


def _verify_google_credential(credential: str | None) -> str:
    token = (credential or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Missing Google credential")
    if not GOOGLE_OAUTH_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_OAUTH_CLIENT_ID is not configured",
        )
    try:
        idinfo = id_token.verify_oauth2_token(token, GoogleTokenRequest(), GOOGLE_OAUTH_CLIENT_ID)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid Google token") from exc

    email = idinfo.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Google account email missing")
    return _require_canonical_email(str(email))


@auth_router.post("/auth/google", response_model=GoogleAuthResponse)
def auth_google(payload: GoogleAuthRequest, response: Response) -> GoogleAuthResponse:
    email = _verify_google_credential(payload.credential)
    session = _sessions().dumps({"email": email, "nonce": secrets.token_urlsafe(12)})
    response.set_cookie(session_cookie(), session, httponly=True, samesite="lax")
    return GoogleAuthResponse(email=email)


@auth_router.get("/auth/callback", response_model=AuthCallbackResponse)
def auth_callback(
    response: Response,
    credential: str | None = None,
    next_path: str = Query(default="/", alias="next"),
) -> AuthCallbackResponse:
    email = _verify_google_credential(credential)
    session = _sessions().dumps({"email": email, "nonce": secrets.token_urlsafe(12)})
    response.set_cookie(session_cookie(), session, httponly=True, samesite="lax")
    return AuthCallbackResponse(email=email, redirect_to=next_path)


@auth_router.post("/auth/logout", response_model=LogoutResponse)
def auth_logout(response: Response) -> LogoutResponse:
    response.delete_cookie(session_cookie())
    return LogoutResponse()


@auth_router.get("/me", response_model=MeResponse)
def me(staff_portal_session: str | None = Cookie(default=None)) -> MeResponse:
    email = current_user_email(staff_portal_session)
    return MeResponse(email=email)


@auth_router.get("/config", response_model=ConfigResponse)
def config() -> ConfigResponse:
    return ConfigResponse(google_client_id=GOOGLE_OAUTH_CLIENT_ID)