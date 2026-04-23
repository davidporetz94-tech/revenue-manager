"""Add revenue_efficiency_zones column to client_configs

Revision ID: d0e4f5a6b7c8
Revises: c9d3e4f5a6b7
Create Date: 2026-03-19 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd0e4f5a6b7c8'
down_revision: Union[str, Sequence[str], None] = 'c9d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('client_configs', sa.Column('revenue_efficiency_zones', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('client_configs', 'revenue_efficiency_zones')
