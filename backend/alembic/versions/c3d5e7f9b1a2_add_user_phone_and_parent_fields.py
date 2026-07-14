"""Add phone and parent contact fields to users

Revision ID: c3d5e7f9b1a2
Revises: b2c4e5f6a7d8
Create Date: 2026-07-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c3d5e7f9b1a2'
down_revision: Union[str, None] = 'b2c4e5f6a7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('phone', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('parent_name', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('parent_phone', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'parent_phone')
    op.drop_column('users', 'parent_name')
    op.drop_column('users', 'phone')
