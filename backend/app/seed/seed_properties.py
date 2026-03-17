"""Seed properties and unit types for Properties A and B."""
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.user import Organization, User
from app.models.property import Property, UnitType


def seed_properties(db: Session) -> dict:
    """Create organization, demo user, 2 properties, and 4 unit types.

    Returns dict of created IDs for downstream seed scripts.
    """
    # Organization
    org = Organization(
        id=uuid.uuid4(),
        name="Demo Client",
        slug="demo-client",
        created_at=datetime.utcnow(),
    )
    db.add(org)
    db.flush()

    # Demo user (password: demo123 — hashed with bcrypt)
    import bcrypt
    pw_hash = bcrypt.hashpw("demo123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    demo_user = User(
        id=uuid.uuid4(),
        email="demo@example.com",
        password_hash=pw_hash,
        full_name="Demo Admin",
        role="admin",
        organization_id=org.id,
        created_at=datetime.utcnow(),
        is_active=True,
    )
    db.add(demo_user)
    db.flush()

    # Property A: 3-story garden-style, Maplewood Gardens submarket
    prop_a = Property(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="Property A",
        code="PROP-A",
        address="100 Maplewood Drive, Springfield, IL 62701",
        submarket="Maplewood Gardens",
        total_units=84,
        year_built=2010,
        property_class="B+",
        created_at=datetime.utcnow(),
    )
    db.add(prop_a)

    # Property B: 4-story mid-rise, Harbor Point submarket
    prop_b = Property(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="Property B",
        code="PROP-B",
        address="250 Harbor Boulevard, Lakeview, IL 60614",
        submarket="Harbor Point",
        total_units=72,
        year_built=2018,
        property_class="A-",
        created_at=datetime.utcnow(),
    )
    db.add(prop_b)
    db.flush()

    # Unit types — base_rent from export
    ut_a1 = UnitType(
        id=uuid.uuid4(),
        property_id=prop_a.id,
        code="A1", bed=1, bath=1,
        total_units=48, base_rent=1240,
        sqft_min=600, sqft_max=650,
    )
    ut_a2 = UnitType(
        id=uuid.uuid4(),
        property_id=prop_a.id,
        code="A2", bed=2, bath=1,
        total_units=36, base_rent=1275,
        sqft_min=850, sqft_max=920,
    )
    ut_b1 = UnitType(
        id=uuid.uuid4(),
        property_id=prop_b.id,
        code="B1", bed=1, bath=1,
        total_units=24, base_rent=1405,
        sqft_min=680, sqft_max=730,
    )
    ut_b2 = UnitType(
        id=uuid.uuid4(),
        property_id=prop_b.id,
        code="B2", bed=2, bath=2,
        total_units=48, base_rent=1465,
        sqft_min=980, sqft_max=1050,
    )
    db.add_all([ut_a1, ut_a2, ut_b1, ut_b2])
    db.flush()

    ids = {
        "org_id": org.id,
        "user_id": demo_user.id,
        "prop_a_id": prop_a.id,
        "prop_b_id": prop_b.id,
        "ut_a1_id": ut_a1.id,
        "ut_a2_id": ut_a2.id,
        "ut_b1_id": ut_b1.id,
        "ut_b2_id": ut_b2.id,
    }
    return ids
