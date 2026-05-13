from __future__ import annotations

from fastapi import FastAPI, Request


def install_security_headers_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)

        csp = "; ".join(
            [
                "default-src 'self'",
                "base-uri 'self'",
                "object-src 'none'",
                "frame-ancestors 'none'",
                "script-src 'self' https://accounts.google.com https://*.gstatic.com",
                "style-src 'self' 'unsafe-inline' https://assets.ubuntu.com",
                "img-src 'self' data: https://*.gstatic.com",
                "font-src 'self' https://assets.ubuntu.com",
                "connect-src 'self' https://accounts.google.com",
                "frame-src https://accounts.google.com",
            ]
        )

        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response