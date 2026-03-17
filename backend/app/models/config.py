import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Boolean, Float, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ClientConfig(Base):
    __tablename__ = "client_configs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    investment_thesis: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_profile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hold_period_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    business_plan_summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    occupancy_thresholds: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    exposure_thresholds: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pricing_tolerance: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    concession_policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    renewal_policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    lease_term_policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    experiment_policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    amenity_benchmarks: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
