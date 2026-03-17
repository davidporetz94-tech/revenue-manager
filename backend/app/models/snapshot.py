import uuid
from datetime import datetime, date

from sqlalchemy import String, Integer, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HistoricalSnapshot(Base):
    __tablename__ = "historical_snapshots"
    __table_args__ = (
        UniqueConstraint("unit_type_id", "snapshot_date", name="uq_snapshot_type_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    unit_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unit_types.id"), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(nullable=False)
    total_units: Mapped[int] = mapped_column(Integer, nullable=False)
    occupied: Mapped[int] = mapped_column(Integer, nullable=False)
    vacant: Mapped[int] = mapped_column(Integer, nullable=False)
    on_notice: Mapped[int] = mapped_column(Integer, nullable=False)
    occupancy_rate: Mapped[float] = mapped_column(Float, nullable=False)
    avg_in_place_rent: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_asking_rent: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_executed_rent: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_days_on_market: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exposure_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    demand_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    comps_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
