from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from itsdangerous import URLSafeSerializer


APP_BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(APP_BASE_DIR / ".env")
SESSIONS = URLSafeSerializer(os.getenv("SESSION_SECRET", "dev-session-secret"), salt="staff-portal")

from .auth.routes import auth_router, current_user_email as _current_user_email, session_cookie as _session_cookie
from .quotes.routes import quotes_router
from .purchases.routes import purchase_router
from .security_headers import install_security_headers_middleware
from .status_check import StatusCheckService


app = FastAPI(title="staff_portal")

api_router = APIRouter(prefix="/api")

FRONTEND_PUBLIC_DIR = APP_BASE_DIR / "frontend" / "public"
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")

# Allow bootstrap-style service account configuration to drive Google client authentication.
if GOOGLE_SERVICE_ACCOUNT_JSON and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_SERVICE_ACCOUNT_JSON


@api_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


api_router.include_router(auth_router)
api_router.include_router(quotes_router)
api_router.include_router(purchase_router)


app.include_router(api_router)


@app.get("/_status/check", include_in_schema=False)
def status_check() -> dict[str, object]:
    return StatusCheckService().run()

install_security_headers_middleware(app)


@app.middleware("http")
async def auth_redirect_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api"):
        return await call_next(request)

    # Public static assets must remain reachable without auth so the login page can boot.
    public_prefixes = (
        "/assets/",
        "/locales/",
    )
    if path.startswith(public_prefixes):
        return await call_next(request)

    allowed = {
        "/login",
        "/login.html",
        "/dist/login.js",
        "/favicon.svg",
        "/settings.svg",
        "/_status/check",
    }
    if path in allowed:
        return await call_next(request)

    token = request.cookies.get(_session_cookie())
    try:
        _current_user_email(token)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=307)

    return await call_next(request)


@app.get("/login", include_in_schema=False)
def login_page() -> FileResponse:
    return FileResponse(FRONTEND_PUBLIC_DIR / "login.html")

app.mount("/", StaticFiles(directory=FRONTEND_PUBLIC_DIR, html=True), name="frontend")
