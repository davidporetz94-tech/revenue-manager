"""Snapshots API endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.snapshot import HistoricalSnapshot
from app.models.property import UnitType

router = APIRouter(prefix="/api/v1", tags=["snapshots"])


@router.get("/properties/{property_id}/snapshots")
def get_snapshots(property_id: str, db: Session = Depends(get_db)):
    """Get historical snapshots for all unit types in a property."""
    unit_types = db.query(UnitType).filter_by(property_id=property_id).all()
    result = {}
    for ut in unit_types:
        snaps = (
            db.query(HistoricalSnapshot)
            .filter_by(unit_type_id=ut.id)
            .order_by(HistoricalSnapshot.snapshot_date)
            .all()
        )
        result[ut.code] = [
            {
                "date": s.snapshot_date.isoformat(),
                "occupancy_rate": s.occupancy_rate,
                "avg_asking_rent": s.avg_asking_rent,
                "avg_executed_rent": s.avg_executed_rent,
                "comps_avg": s.comps_avg,
                "demand_score": s.demand_score,
                "exposure_pct": s.exposure_pct,
            }
            for s in snaps
        ]
    return result
