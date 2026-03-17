"""Master seed script — runs all seed scripts in dependency order.

Usage: cd backend && python -m app.seed.seed_all
"""
from app.database import SessionLocal
from app.seed.seed_properties import seed_properties
from app.seed.seed_units import seed_units
from app.seed.seed_comps import seed_comps
from app.seed.seed_snapshots import seed_snapshots
from app.seed.seed_config import seed_config


def run_all_seeds() -> None:
    db = SessionLocal()
    try:
        # Clear existing data in reverse dependency order
        from app.models.experiment import ExperimentAssignment, Experiment
        from app.models.diagnostic import DiagnosticRun, AuditLog
        from app.models.snapshot import HistoricalSnapshot
        from app.models.config import ClientConfig
        from app.models.comp import CompRent, CompUnitType, CompProperty
        from app.models.property import Unit, UnitType, Property
        from app.models.user import User, Organization

        db.query(ExperimentAssignment).delete()
        db.query(Experiment).delete()
        db.query(AuditLog).delete()
        db.query(DiagnosticRun).delete()
        db.query(HistoricalSnapshot).delete()
        db.query(ClientConfig).delete()
        db.query(CompRent).delete()
        db.query(CompUnitType).delete()
        db.query(CompProperty).delete()
        db.query(Unit).delete()
        db.query(UnitType).delete()
        db.query(Property).delete()
        db.query(User).delete()
        db.query(Organization).delete()
        db.flush()

        print("Seeding properties and unit types...")
        ids = seed_properties(db)
        print(f"  Created org={ids['org_id']}, 2 properties, 4 unit types")

        print("Seeding units (156 total)...")
        seed_units(db, ids)
        print("  156 units seeded")

        print("Seeding comp properties and rents...")
        seed_comps(db, ids)
        print("  9 comp properties, 72 rent observations")

        print("Seeding historical snapshots...")
        seed_snapshots(db, ids)
        print("  16 snapshots (4 unit types × 4 months)")

        print("Seeding client configs...")
        seed_config(db, ids)
        print("  2 configs (1 per property)")

        db.commit()
        print("\nAll seeds committed successfully.")

    except Exception as e:
        db.rollback()
        print(f"\nSeed FAILED: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_all_seeds()
