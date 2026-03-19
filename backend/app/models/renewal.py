"""Renewal rule and output models.

Rules are set per floorplan per target month. Outputs are computed
per-unit renewal prices generated from those rules.
"""
import uuid
from datetime import datetime, date

from sqlalchemy import String, Float, Integer, Date, ForeignKey, JSON, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RenewalRule(Base):
    """Renewal pricing rule for a floorplan in a target month."""

    __tablename__ = "renewal_rules"
    __table_args__ = (
        CheckConstraint(
            "calc_method IN ('DISCOUNT_FROM_NEW', 'INCREASE_FROM_IN_PLACE')",
            name="ck_renewal_rules_calc_method",
        ),
        Index(
            "ix_renewal_rules_prop_month",
            "property_id",
            "target_month",
        ),
        Index(
            "ix_renewal_rules_org_month",
            "organization_id",
            "target_month",
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
    target_month: Mapped[date] = mapped_column(Date, nullable=False)
    calc_method: Mapped[str] = mapped_column(String(30), nullable=False)
    calc_value: Mapped[float] = mapped_column(Float, nullable=False)
    min_increase_pct: Mapped[float] = mapped_column(Float, nullable=False)
    max_increase_pct: Mapped[float] = mapped_column(Float, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class RenewalOutput(Base):
    """Computed per-unit renewal price from a rule."""

    __tablename__ = "renewal_outputs"
    __table_args__ = (
        Index("ix_renewal_outputs_rule", "rule_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("renewal_rules.id"), nullable=False
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("units.id"), nullable=False
    )
    unit_number: Mapped[str] = mapped_column(String(20), nullable=False)
    in_place_rent: Mapped[float] = mapped_column(Float, nullable=False)
    new_lease_rent: Mapped[float] = mapped_column(Float, nullable=False)
    computed_renewal_rent: Mapped[float] = mapped_column(Float, nullable=False)
    effective_increase_pct: Mapped[float] = mapped_column(Float, nullable=False)
    was_clamped: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # None, 'MIN', or 'MAX'
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
