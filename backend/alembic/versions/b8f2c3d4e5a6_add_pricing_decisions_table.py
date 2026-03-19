"""add pricing_decisions table

Revision ID: b8f2c3d4e5a6
Revises: a43e41e547e9
Create Date: 2026-03-18 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8f2c3d4e5a6'
down_revision: Union[str, Sequence[str], None] = 'a43e41e547e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pricing_decisions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('property_id', sa.Uuid(), nullable=False),
        sa.Column('unit_type_code', sa.String(length=20), nullable=False),
        sa.Column('decision_type', sa.String(length=20), nullable=False),
        sa.Column('decision', sa.String(length=20), nullable=False),
        sa.Column('recommended_value', sa.Float(), nullable=False),
        sa.Column('approved_value', sa.Float(), nullable=True),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.Column('decided_by', sa.Uuid(), nullable=False),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('context_snapshot', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['property_id'], ['properties.id']),
        sa.ForeignKeyConstraint(['decided_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "decision_type IN ('PRICING', 'RENEWAL')",
            name='ck_pricing_decisions_type',
        ),
        sa.CheckConstraint(
            "decision IN ('APPROVE', 'HOLD', 'MODIFY')",
            name='ck_pricing_decisions_decision',
        ),
    )
    op.create_index(
        'ix_pricing_decisions_org_type_date',
        'pricing_decisions',
        ['organization_id', 'decision_type', 'decided_at'],
    )
    op.create_index(
        'ix_pricing_decisions_prop_unit_date',
        'pricing_decisions',
        ['property_id', 'unit_type_code', 'decided_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_pricing_decisions_prop_unit_date', table_name='pricing_decisions')
    op.drop_index('ix_pricing_decisions_org_type_date', table_name='pricing_decisions')
    op.drop_table('pricing_decisions')
