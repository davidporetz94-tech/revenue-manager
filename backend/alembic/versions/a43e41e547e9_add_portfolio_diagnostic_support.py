"""add portfolio diagnostic support

Revision ID: a43e41e547e9
Revises: 77e354e140ab
Create Date: 2026-03-18 15:19:49.140466

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a43e41e547e9'
down_revision: Union[str, Sequence[str], None] = '77e354e140ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add organization_id, scope columns; make property_id nullable."""
    # Step 1: Add organization_id as nullable first
    op.add_column('diagnostic_runs', sa.Column('organization_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_diagnostic_runs_org', 'diagnostic_runs', 'organizations', ['organization_id'], ['id'])

    # Step 2: Backfill from properties table
    op.execute("""
        UPDATE diagnostic_runs dr
        SET organization_id = p.organization_id
        FROM properties p
        WHERE dr.property_id = p.id
    """)

    # Step 3: Make NOT NULL after backfill
    op.alter_column('diagnostic_runs', 'organization_id', nullable=False)

    # Step 4: Add scope column with check constraint
    op.add_column('diagnostic_runs', sa.Column('scope', sa.String(length=20), server_default='property', nullable=False))
    op.create_check_constraint('ck_diagnostic_runs_scope', 'diagnostic_runs', "scope IN ('property', 'portfolio')")

    # Step 5: Make property_id nullable (portfolio runs have NULL)
    op.alter_column('diagnostic_runs', 'property_id', existing_type=sa.UUID(), nullable=True)

    # Step 6: Index for portfolio history queries
    op.create_index('ix_diagnostic_runs_portfolio', 'diagnostic_runs', ['organization_id', 'scope', 'run_date'], unique=False)


def downgrade() -> None:
    """Remove portfolio support — deletes any portfolio runs."""
    op.drop_index('ix_diagnostic_runs_portfolio', table_name='diagnostic_runs')

    # Delete portfolio runs first (they have NULL property_id)
    op.execute("DELETE FROM diagnostic_runs WHERE scope = 'portfolio'")

    op.alter_column('diagnostic_runs', 'property_id', existing_type=sa.UUID(), nullable=False)
    op.drop_constraint('ck_diagnostic_runs_scope', 'diagnostic_runs', type_='check')
    op.drop_column('diagnostic_runs', 'scope')
    op.drop_constraint('fk_diagnostic_runs_org', 'diagnostic_runs', type_='foreignkey')
    op.drop_column('diagnostic_runs', 'organization_id')
