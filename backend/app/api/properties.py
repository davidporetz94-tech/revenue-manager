"""Properties API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.property import Property, UnitType, Unit
from app.models.user import User

router = APIRouter(prefix="/api/v1", tags=["properties"])


def _get_demo_user(db: Session) -> User:
    user = db.query(User).filter_by(email="demo@example.com").first()
    if not user:
        raise HTTPException(status_code=500, detail="Demo user not found")
    return user


@router.get("/properties")
def list_properties(db: Session = Depends(get_db)):
    """List all properties for the current user's organization."""
    user = _get_demo_user(db)
    props = db.query(Property).filter_by(organization_id=user.organization_id).all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "code": p.code,
            "address": p.address,
            "submarket": p.submarket,
            "total_units": p.total_units,
            "year_built": p.year_built,
            "property_class": p.property_class,
        }
        for p in props
    ]


@router.get("/properties/{property_id}")
def get_property(property_id: str, db: Session = Depends(get_db)):
    """Get a single property by ID."""
    prop = db.query(Property).filter_by(id=property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return {
        "id": str(prop.id),
        "name": prop.name,
        "code": prop.code,
        "address": prop.address,
        "submarket": prop.submarket,
        "total_units": prop.total_units,
        "year_built": prop.year_built,
        "property_class": prop.property_class,
    }
