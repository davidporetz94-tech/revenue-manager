import uuid
from datetime import datetime, date

from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CompProperty(Base):
    __tablename__ = "comp_properties"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    submarket: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_built: Mapped[int | None] = mapped_column(Integer, nullable=True)
    property_class: Mapped[str | None] = mapped_column(String(10), nullable=True)
    distance_miles: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    comp_unit_types: Mapped[list["CompUnitType"]] = relationship(back_populates="comp_property")


class CompUnitType(Base):
    __tablename__ = "comp_unit_types"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    comp_property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("comp_properties.id"), nullable=False)
    subject_unit_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unit_types.id"), nullable=False)
    bed: Mapped[int] = mapped_column(Integer, nullable=False)
    bath: Mapped[int] = mapped_column(Integer, nullable=False)
    sqft_range: Mapped[str | None] = mapped_column(String(50), nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    comp_property: Mapped["CompProperty"] = relationship(back_populates="comp_unit_types")
    comp_rents: Mapped[list["CompRent"]] = relationship(back_populates="comp_unit_type")


class CompRent(Base):
    """PUBLIC DATA ONLY — asking rents from public sources. Never competitor
    effective rents, occupancy, or concession details."""
    __tablename__ = "comp_rents"
    __table_args__ = (
        Index("ix_comp_rents_type_date", "comp_unit_type_id", "observation_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    comp_unit_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("comp_unit_types.id"), nullable=False)
    observation_date: Mapped[date] = mapped_column(nullable=False)
    asking_rent: Mapped[float] = mapped_column(Float, nullable=False)
    concession_advertised: Mapped[str | None] = mapped_column(String(255), nullable=True)
    net_effective_rent: Mapped[float | None] = mapped_column(Float, nullable=True)
    units_advertised: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    data_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    comp_unit_type: Mapped["CompUnitType"] = relationship(back_populates="comp_rents")
