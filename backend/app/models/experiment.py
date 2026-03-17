import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    diagnostic_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("diagnostic_runs.id"), nullable=False)
    unit_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unit_types.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PROPOSED")
    experiment_design: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    outcome_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class ExperimentAssignment(Base):
    __tablename__ = "experiment_assignments"
    __table_args__ = (
        UniqueConstraint("experiment_id", "unit_id", name="uq_experiment_unit"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiments.id"), nullable=False)
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units.id"), nullable=False)
    arm_label: Mapped[str] = mapped_column(String(50), nullable=False)
    assigned_price: Mapped[float] = mapped_column(Float, nullable=False)
    assigned_concession: Mapped[str | None] = mapped_column(String(255), nullable=True)
    leased: Mapped[bool] = mapped_column(Boolean, default=False)
    lease_date: Mapped[datetime | None] = mapped_column(nullable=True)
    days_to_lease: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application_received: Mapped[bool] = mapped_column(Boolean, default=False)
    application_date: Mapped[datetime | None] = mapped_column(nullable=True)
    tours_count: Mapped[int] = mapped_column(Integer, default=0)
