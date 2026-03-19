"""Pydantic schemas for pricing/renewal decision endpoints."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator


class PricingDecisionCreate(BaseModel):
    """Request body for creating a pricing/renewal decision."""

    property_id: str
    unit_type_code: str
    decision_type: Literal["PRICING", "RENEWAL"]
    decision: Literal["APPROVE", "HOLD", "MODIFY"]
    recommended_value: float
    approved_value: float | None = None
    reason: str | None = None
    context_snapshot: dict | None = None

    @model_validator(mode="after")
    def validate_decision_fields(self) -> "PricingDecisionCreate":
        """Cross-field validation for decision-specific requirements."""
        if self.decision == "MODIFY" and self.approved_value is None:
            raise ValueError("approved_value is required for MODIFY decisions")
        if self.decision == "HOLD" and not self.reason:
            raise ValueError("reason is required for HOLD decisions")
        if self.decision == "APPROVE":
            self.approved_value = self.recommended_value
        return self


class PricingDecisionBatchCreate(BaseModel):
    """Request body for batch creating decisions."""

    decisions: list[PricingDecisionCreate]

    @model_validator(mode="after")
    def validate_batch_size(self) -> "PricingDecisionBatchCreate":
        """Limit batch size to 20."""
        if len(self.decisions) > 20:
            raise ValueError("Batch size cannot exceed 20 decisions")
        if len(self.decisions) == 0:
            raise ValueError("At least one decision is required")
        return self


class PricingDecisionResponse(BaseModel):
    """Full decision response with user name."""

    id: str
    organization_id: str
    property_id: str
    unit_type_code: str
    decision_type: str
    decision: str
    recommended_value: float
    approved_value: float | None = None
    reason: str | None = None
    decided_by: str
    decided_by_name: str | None = None
    decided_at: datetime
    context_snapshot: dict | None = None

    model_config = {"from_attributes": True}


class PricingDecisionLatest(BaseModel):
    """Compact latest decision per unit type."""

    unit_type_code: str
    decision: str
    decided_at: datetime
    approved_value: float | None = None
    decided_by_name: str | None = None

    model_config = {"from_attributes": True}
