"""add renewal_rules and renewal_outputs tables

Revision ID: c9d3e4f5a6b7
Revises: b8f2c3d4e5a6
Create Date: 2026-03-18 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'b8f2c3d4e5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'renewal_rules',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('property_id', sa.Uuid(), nullable=False),
        sa.Column('unit_type_code', sa.String(length=20), nullable=False),
        sa.Column('target_month', sa.Date(), nullable=False),
        sa.Column('calc_method', sa.String(length=30), nullable=False),
        sa.Column('calc_value', sa.Float(), nullable=False),
        sa.Column('min_increase_pct', sa.Float(), nullable=False),
        sa.Column('max_increase_pct', sa.Float(), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['property_id'], ['properties.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "calc_method IN ('DISCOUNT_FROM_NEW', 'INCREASE_FROM_IN_PLACE')",
            name='ck_renewal_rules_calc_method',
        ),
    )
    op.create_index(
        'ix_renewal_rules_prop_month', 'renewal_rules',
        ['property_id', 'target_month'],
    )
    op.create_index(
        'ix_renewal_rules_org_month', 'renewal_rules',
        ['organization_id', 'target_month'],
    )

    op.create_table(
        'renewal_outputs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('rule_id', sa.Uuid(), nullable=False),
        sa.Column('unit_id', sa.Uuid(), nullable=False),
        sa.Column('unit_number', sa.String(length=20), nullable=False),
        sa.Column('in_place_rent', sa.Float(), nullable=False),
        sa.Column('new_lease_rent', sa.Float(), nullable=False),
        sa.Column('computed_renewal_rent', sa.Float(), nullable=False),
        sa.Column('effective_increase_pct', sa.Float(), nullable=False),
        sa.Column('was_clamped', sa.String(length=10), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['rule_id'], ['renewal_rules.id']),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_renewal_outputs_rule', 'renewal_outputs', ['rule_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_renewal_outputs_rule', table_name='renewal_outputs')
    op.drop_table('renewal_outputs')
    op.drop_index('ix_renewal_rules_org_month', table_name='renewal_rules')
    op.drop_index('ix_renewal_rules_prop_month', table_name='renewal_rules')
    op.drop_table('renewal_rules')
