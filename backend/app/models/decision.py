"""Pricing and renewal decision tracking model.

Append-only table — no UPDATE or DELETE operations permitted.
Follows the AuditLog pattern from diagnostic.py.
"""
import uuid
from datetime import datetime

from sqlalchemy import String, Float, ForeignKey, JSON, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PricingDecision(Base):
    """APPEND-ONLY pricing/renewal decision log. No update or delete operations permitted."""

    __tablename__ = "pricing_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision_type IN ('PRICING', 'RENEWAL')",
            name="ck_pricing_decisions_type",
        ),
        CheckConstraint(
            "decision IN ('APPROVE', 'HOLD', 'MODIFY')",
            name="ck_pricing_decisions_decision",
        ),
        Index(
            "ix_pricing_decisions_org_type_date",
            "organization_id",
            "decision_type",
            "decided_at",
        ),
        Index(
            "ix_pricing_decisions_prop_unit_date",
            "property_id",
            "unit_type_code",
            "decided_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("properties.id"), nullable=False
    )
    unit_type_code: Mapped[str] = mapped_column(String(20), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(20), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    recommended_value: Mapped[float] = mapped_column(Float, nullable=False)
    approved_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    decided_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    decided_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    context_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
