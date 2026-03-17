"""Test auth endpoints — login, register, JWT verification."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User

client = TestClient(app)


class TestLogin:
    def test_login_success(self):
        res = client.post("/api/v1/auth/login", json={
            "email": "demo@example.com",
            "password": "demo123",
        })
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "demo@example.com"
        assert data["user"]["role"] == "admin"

    def test_login_wrong_password(self):
        res = client.post("/api/v1/auth/login", json={
            "email": "demo@example.com",
            "password": "wrongpassword",
        })
        assert res.status_code == 401

    def test_login_nonexistent_user(self):
        res = client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "whatever",
        })
        assert res.status_code == 401


class TestRegister:
    def test_register_success(self):
        res = client.post("/api/v1/auth/register", json={
            "email": "newuser@test.com",
            "password": "testpassword123",
            "full_name": "Test User",
            "organization_name": "Test Org",
        })
        assert res.status_code == 200
        assert "user_id" in res.json()

        # Clean up
        db = SessionLocal()
        user = db.query(User).filter_by(email="newuser@test.com").first()
        if user:
            from app.models.user import Organization
            db.delete(user)
            org = db.query(Organization).filter_by(id=user.organization_id).first()
            if org:
                db.delete(org)
            db.commit()
        db.close()

    def test_register_duplicate_email(self):
        res = client.post("/api/v1/auth/register", json={
            "email": "demo@example.com",
            "password": "testpassword123",
            "full_name": "Duplicate",
            "organization_name": "Dupe Org",
        })
        assert res.status_code == 400

    def test_register_short_password(self):
        res = client.post("/api/v1/auth/register", json={
            "email": "short@test.com",
            "password": "123",
            "full_name": "Short",
            "organization_name": "Short Org",
        })
        assert res.status_code == 422  # Pydantic validation


class TestProtectedEndpoints:
    def test_properties_without_token(self):
        """Properties endpoint falls back to demo user (MVP mode)."""
        res = client.get("/api/v1/properties")
        assert res.status_code == 200

    def test_properties_with_token(self):
        login = client.post("/api/v1/auth/login", json={
            "email": "demo@example.com",
            "password": "demo123",
        })
        token = login.json()["access_token"]
        res = client.get("/api/v1/properties", headers={
            "Authorization": f"Bearer {token}",
        })
        assert res.status_code == 200
        props = res.json()
        assert len(props) == 2
        names = {p["name"] for p in props}
        assert names == {"Property A", "Property B"}

    def test_auth_me(self):
        login = client.post("/api/v1/auth/login", json={
            "email": "demo@example.com",
            "password": "demo123",
        })
        token = login.json()["access_token"]
        res = client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == "demo@example.com"
        assert data["organization_name"] == "Demo Client"


class TestConfigEndpoints:
    def test_get_config(self):
        props = client.get("/api/v1/properties").json()
        prop_id = props[0]["id"]
        res = client.get(f"/api/v1/properties/{prop_id}/config")
        assert res.status_code == 200
        data = res.json()
        assert data["is_active"] is True
        assert "occupancy_thresholds" in data

    def test_config_preview(self):
        props = client.get("/api/v1/properties").json()
        prop_id = props[0]["id"]
        config = client.get(f"/api/v1/properties/{prop_id}/config").json()
        res = client.post(f"/api/v1/properties/{prop_id}/config/preview", json={
            "occupancy_thresholds": config["occupancy_thresholds"],
            "exposure_thresholds": config["exposure_thresholds"],
            "pricing_tolerance": config["pricing_tolerance"],
            "concession_policy": config["concession_policy"],
            "renewal_policy": config["renewal_policy"],
            "lease_term_policy": config["lease_term_policy"],
            "experiment_policy": config["experiment_policy"],
            "amenity_benchmarks": config["amenity_benchmarks"],
        })
        assert res.status_code == 200
        data = res.json()
        # Should have flag counts for unit types in this property
        assert len(data) >= 1


class TestCompEndpoints:
    def test_get_comps(self):
        props = client.get("/api/v1/properties").json()
        prop_id = props[0]["id"]
        res = client.get(f"/api/v1/properties/{prop_id}/comps")
        assert res.status_code == 200
        comps = res.json()
        assert len(comps) >= 1

    def test_get_comp_trends(self):
        props = client.get("/api/v1/properties").json()
        prop_id = props[0]["id"]
        res = client.get(f"/api/v1/properties/{prop_id}/comps/trends")
        assert res.status_code == 200


class TestSnapshotEndpoint:
    def test_get_snapshots(self):
        props = client.get("/api/v1/properties").json()
        prop_id = props[0]["id"]
        res = client.get(f"/api/v1/properties/{prop_id}/snapshots")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1


class TestAuditEndpoint:
    def test_get_audit_log(self):
        res = client.get("/api/v1/audit")
        assert res.status_code == 200
