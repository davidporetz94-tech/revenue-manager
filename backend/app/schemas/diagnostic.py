"""Pydantic schemas for diagnostic API endpoints."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DiagnosticRunResponse(BaseModel):
    id: str
    property_id: str | None = None
    scope: str = "property"
    status: str
    run_date: datetime | None = None
    metrics_json: dict | None = None
    flags_json: dict | None = None
    diagnosis_json: dict | None = None
    action_plan_json: dict | None = None
    error_message: str | None = None
    metrics_compute_ms: int | None = None
    diagnosis_api_ms: int | None = None
    action_plan_api_ms: int | None = None
    total_ms: int | None = None

    model_config = {"from_attributes": True}


class DiagnosticRunCreate(BaseModel):
    """Request body for triggering a diagnostic run."""
    pass  # No body needed — property_id from URL, user from JWT


class DiagnosticRunSummary(BaseModel):
    id: str
    property_id: str | None = None
    scope: str = "property"
    status: str
    run_date: datetime | None = None
    total_ms: int | None = None

    model_config = {"from_attributes": True}
