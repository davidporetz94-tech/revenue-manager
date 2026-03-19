"""Tests for pricing decision endpoints."""
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.user import Organization, User
from app.models.property import Property
from app.models.decision import PricingDecision
from app.auth.dependencies import get_current_user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite:///./test_decisions.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def setup_db():
    """Create fresh tables for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def org(db):
    org = Organization(
        id=uuid.uuid4(), name="Test Org", slug="test-org"
    )
    db.add(org)
    db.commit()
    return org


@pytest.fixture()
def user(db, org):
    u = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash="hashed",
        full_name="Test User",
        role="admin",
        organization_id=org.id,
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture()
def prop(db, org):
    p = Property(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="Test Property",
        code="TP",
        address="123 Test St",
        submarket="Test Submarket",
        total_units=100,
    )
    db.add(p)
    db.commit()
    return p


@pytest.fixture()
def client(db, user):
    """Test client with DB and auth overrides."""
    def override_db():
        try:
            yield db
        finally:
            pass

    def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCreateDecision:
    """POST /api/v1/pricing-decisions"""

    def test_approve_decision(self, client, prop):
        """APPROVE sets approved_value to recommended_value."""
        resp = client.post("/api/v1/pricing-decisions", json={
            "property_id": str(prop.id),
            "unit_type_code": "A1",
            "decision_type": "PRICING",
            "decision": "APPROVE",
            "recommended_value": 1365.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "APPROVE"
        assert data["approved_value"] == 1365.0
        assert data["unit_type_code"] == "A1"
        assert data["decided_by_name"] == "Test User"

    def test_hold_requires_reason(self, client, prop):
        """HOLD without reason is rejected."""
        resp = client.post("/api/v1/pricing-decisions", json={
            "property_id": str(prop.id),
            "unit_type_code": "A1",
            "decision_type": "PRICING",
            "decision": "HOLD",
            "recommended_value": 1365.0,
        })
        assert resp.status_code == 422

    def test_hold_with_reason(self, client, prop):
        """HOLD with reason succeeds."""
        resp = client.post("/api/v1/pricing-decisions", json={
            "property_id": str(prop.id),
            "unit_type_code": "A2",
            "decision_type": "PRICING",
            "decision": "HOLD",
            "recommended_value": 1411.0,
            "reason": "Market uncertainty",
        })
        assert resp.status_code == 200
        assert resp.json()["reason"] == "Market uncertainty"

    def test_modify_requires_approved_value(self, client, prop):
        """MODIFY without approved_value is rejected."""
        resp = client.post("/api/v1/pricing-decisions", json={
            "property_id": str(prop.id),
            "unit_type_code": "A1",
            "decision_type": "PRICING",
            "decision": "MODIFY",
            "recommended_value": 1365.0,
        })
        assert resp.status_code == 422

    def test_modify_with_approved_value(self, client, prop):
        """MODIFY with custom approved_value succeeds."""
        resp = client.post("/api/v1/pricing-decisions", json={
            "property_id": str(prop.id),
            "unit_type_code": "A1",
            "decision_type": "PRICING",
            "decision": "MODIFY",
            "recommended_value": 1365.0,
            "approved_value": 1350.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved_value"] == 1350.0

    def test_invalid_property_404(self, client):
        """Decision for non-existent property returns 404."""
        resp = client.post("/api/v1/pricing-decisions", json={
            "property_id": str(uuid.uuid4()),
            "unit_type_code": "A1",
            "decision_type": "PRICING",
            "decision": "APPROVE",
            "recommended_value": 1365.0,
        })
        assert resp.status_code == 404

    def test_renewal_decision(self, client, prop):
        """RENEWAL type decisions work."""
        resp = client.post("/api/v1/pricing-decisions", json={
            "property_id": str(prop.id),
            "unit_type_code": "A1",
            "decision_type": "RENEWAL",
            "decision": "APPROVE",
            "recommended_value": 1300.0,
        })
        assert resp.status_code == 200
        assert resp.json()["decision_type"] == "RENEWAL"


class TestBatchDecisions:
    """POST /api/v1/pricing-decisions/batch"""

    def test_batch_approve(self, client, prop):
        """Batch creation of multiple decisions."""
        resp = client.post("/api/v1/pricing-decisions/batch", json={
            "decisions": [
                {
                    "property_id": str(prop.id),
                    "unit_type_code": "A1",
                    "decision_type": "PRICING",
                    "decision": "APPROVE",
                    "recommended_value": 1365.0,
                },
                {
                    "property_id": str(prop.id),
                    "unit_type_code": "A2",
                    "decision_type": "PRICING",
                    "decision": "APPROVE",
                    "recommended_value": 1411.0,
                },
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 2
        assert len(data["decisions"]) == 2

    def test_batch_empty_rejected(self, client):
        """Empty batch is rejected."""
        resp = client.post("/api/v1/pricing-decisions/batch", json={
            "decisions": []
        })
        assert resp.status_code == 422

    def test_batch_over_limit_rejected(self, client, prop):
        """Batch over 20 is rejected."""
        decisions = [
            {
                "property_id": str(prop.id),
                "unit_type_code": f"U{i}",
                "decision_type": "PRICING",
                "decision": "APPROVE",
                "recommended_value": 1000.0 + i,
            }
            for i in range(21)
        ]
        resp = client.post("/api/v1/pricing-decisions/batch", json={
            "decisions": decisions
        })
        assert resp.status_code == 422


class TestListDecisions:
    """GET /api/v1/pricing-decisions"""

    def test_list_empty(self, client):
        """Empty list when no decisions exist."""
        resp = client.get("/api/v1/pricing-decisions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_filters(self, client, prop):
        """Filters work correctly."""
        # Create a pricing and renewal decision
        client.post("/api/v1/pricing-decisions", json={
            "property_id": str(prop.id),
            "unit_type_code": "A1",
            "decision_type": "PRICING",
            "decision": "APPROVE",
            "recommended_value": 1365.0,
        })
        client.post("/api/v1/pricing-decisions", json={
            "property_id": str(prop.id),
            "unit_type_code": "A1",
            "decision_type": "RENEWAL",
            "decision": "APPROVE",
            "recommended_value": 1300.0,
        })

        # Filter by type
        resp = client.get("/api/v1/pricing-decisions", params={"decision_type": "PRICING"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["decision_type"] == "PRICING"

        # Filter by property
        resp = client.get("/api/v1/pricing-decisions", params={"property_id": str(prop.id)})
        assert len(resp.json()) == 2


class TestLatestDecisions:
    """GET /api/v1/pricing-decisions/latest"""

    def test_latest_per_unit_type(self, client, prop):
        """Returns only the most recent decision per unit type."""
        # Create two decisions for same unit type
        client.post("/api/v1/pricing-decisions", json={
            "property_id": str(prop.id),
            "unit_type_code": "A1",
            "decision_type": "PRICING",
            "decision": "HOLD",
            "recommended_value": 1365.0,
            "reason": "Waiting on market data",
        })
        client.post("/api/v1/pricing-decisions", json={
            "property_id": str(prop.id),
            "unit_type_code": "A1",
            "decision_type": "PRICING",
            "decision": "APPROVE",
            "recommended_value": 1365.0,
        })

        resp = client.get("/api/v1/pricing-decisions/latest", params={
            "property_id": str(prop.id),
            "decision_type": "PRICING",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["unit_type_code"] == "A1"
        assert data[0]["decision"] == "APPROVE"  # Latest one

    def test_latest_multiple_unit_types(self, client, prop):
        """Returns latest for each unit type."""
        client.post("/api/v1/pricing-decisions", json={
            "property_id": str(prop.id),
            "unit_type_code": "A1",
            "decision_type": "PRICING",
            "decision": "APPROVE",
            "recommended_value": 1365.0,
        })
        client.post("/api/v1/pricing-decisions", json={
            "property_id": str(prop.id),
            "unit_type_code": "B1",
            "decision_type": "PRICING",
            "decision": "HOLD",
            "recommended_value": 1525.0,
            "reason": "Occupancy concerns",
        })

        resp = client.get("/api/v1/pricing-decisions/latest", params={
            "property_id": str(prop.id),
            "decision_type": "PRICING",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        codes = {d["unit_type_code"] for d in data}
        assert codes == {"A1", "B1"}


class TestAuditLogging:
    """Verify decisions create audit log entries."""

    def test_decision_creates_audit(self, client, prop, db):
        """Each decision creates an audit log entry."""
        from app.models.diagnostic import AuditLog

        client.post("/api/v1/pricing-decisions", json={
            "property_id": str(prop.id),
            "unit_type_code": "A1",
            "decision_type": "PRICING",
            "decision": "APPROVE",
            "recommended_value": 1365.0,
        })

        audits = db.query(AuditLog).filter(
            AuditLog.action == "PRICING_DECISION_APPROVE"
        ).all()
        assert len(audits) == 1
        assert audits[0].entity_type == "pricing_decision"
        assert audits[0].details["unit_type_code"] == "A1"
