import uuid
from datetime import datetime

from sqlalchemy import String, Integer, ForeignKey, JSON, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DiagnosticRun(Base):
    __tablename__ = "diagnostic_runs"
    __table_args__ = (
        CheckConstraint("scope IN ('property', 'portfolio')", name="ck_diagnostic_runs_scope"),
        Index("ix_diagnostic_runs_portfolio", "organization_id", "scope", "run_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("properties.id"), nullable=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, server_default="property")
    config_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("client_configs.id"), nullable=True)
    run_date: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    flags_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    diagnosis_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    action_plan_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    narrative_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    slide_deck_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    metrics_compute_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diagnosis_api_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action_plan_api_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    narrative_api_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AuditLog(Base):
    """APPEND-ONLY audit log. No update or delete operations permitted."""
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_org_created", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
