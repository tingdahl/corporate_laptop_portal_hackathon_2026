from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GoogleAuthRequest(ContractModel):
    credential: str | None = Field(default=None, description="Google ID token credential.")


class GoogleAuthResponse(ContractModel):
    email: str


class MeResponse(ContractModel):
    email: str


class ConfigResponse(ContractModel):
    google_client_id: str


class LogoutResponse(ContractModel):
    status: str = "ok"


class AuthCallbackResponse(ContractModel):
    email: str
    redirect_to: str = "/"