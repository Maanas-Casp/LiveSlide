from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str


class ReviewRequest(BaseModel):
    decision: Literal["accepted", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


class RejectAlertRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class AlertDraftRequest(BaseModel):
    run_id: str
    facts: dict
    texts: dict


class ScoreItem(BaseModel):
    cell_id: str
    ts: datetime
    risk_p: float = Field(ge=0, le=1)
    action: Literal["IGNORE", "WATCH", "VERIFY", "WARN"]
    model_version: str
    synthetic: bool = False


class FeatureItem(BaseModel):
    cell_id: str
    ts: datetime
    rain_1d: float | None = None
    rain_3d: float | None = None
    rain_7d: float | None = None
    rain_20d: float | None = None
    soil_moisture: float | None = None
    source_version: str = "unknown"
    synthetic: bool = False
