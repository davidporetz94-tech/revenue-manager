import uuid
from datetime import datetime, date

from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Property(Base):
    __tablename__ = "properties"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_property_org_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    submarket: Mapped[str] = mapped_column(String(100), nullable=False)
    total_units: Mapped[int] = mapped_column(Integer, nullable=False)
    year_built: Mapped[int | None] = mapped_column(Integer, nullable=True)
    property_class: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    unit_types: Mapped[list["UnitType"]] = relationship(back_populates="property")
    units: Mapped[list["Unit"]] = relationship(back_populates="property")


class UnitType(Base):
    __tablename__ = "unit_types"
    __table_args__ = (
        UniqueConstraint("property_id", "code", name="uq_unittype_prop_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    bed: Mapped[int] = mapped_column(Integer, nullable=False)
    bath: Mapped[int] = mapped_column(Integer, nullable=False)
    total_units: Mapped[int] = mapped_column(Integer, nullable=False)
    base_rent: Mapped[float] = mapped_column(Float, nullable=False)
    sqft_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sqft_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    property: Mapped["Property"] = relationship(back_populates="unit_types")
    units: Mapped[list["Unit"]] = relationship(back_populates="unit_type")


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("property_id", "unit_number", name="uq_unit_prop_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    unit_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unit_types.id"), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"), nullable=False)
    unit_number: Mapped[str] = mapped_column(String(20), nullable=False)
    floor: Mapped[int] = mapped_column(Integer, nullable=False)
    sqft: Mapped[int] = mapped_column(Integer, nullable=False)

    # Amenity booleans
    premium_view: Mapped[bool] = mapped_column(Boolean, default=False)
    high_floor: Mapped[bool] = mapped_column(Boolean, default=False)
    corner_unit: Mapped[bool] = mapped_column(Boolean, default=False)
    in_unit_wd: Mapped[bool] = mapped_column(Boolean, default=False)
    renovated: Mapped[bool] = mapped_column(Boolean, default=False)
    patio_balcony: Mapped[bool] = mapped_column(Boolean, default=False)
    ev_charging: Mapped[bool] = mapped_column(Boolean, default=False)
    garage_parking: Mapped[bool] = mapped_column(Boolean, default=False)

    amenity_premium: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    predicted_rent: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    current_rent: Mapped[float | None] = mapped_column(Float, nullable=True)
    lease_start: Mapped[date | None] = mapped_column(nullable=True)
    lease_end: Mapped[date | None] = mapped_column(nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    asking_rent: Mapped[float | None] = mapped_column(Float, nullable=True)
    days_on_market: Mapped[int | None] = mapped_column(Integer, nullable=True)
    days_vacant: Mapped[int | None] = mapped_column(Integer, nullable=True)
    move_out_date: Mapped[date | None] = mapped_column(nullable=True)
    last_executed_rent: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_executed_date: Mapped[date | None] = mapped_column(nullable=True)
    concession_active: Mapped[bool] = mapped_column(Boolean, default=False)
    concession_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    concession_value_monthly: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    unit_type: Mapped["UnitType"] = relationship(back_populates="units")
    property: Mapped["Property"] = relationship(back_populates="units")
