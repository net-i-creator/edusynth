"""Add education_level, grade_label, user role

Revision ID: b2c4e5f6a7d8
Revises: daa3f2c180f3
Create Date: 2026-07-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b2c4e5f6a7d8'
down_revision: Union[str, None] = 'daa3f2c180f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE education_level AS ENUM ('school', 'university', 'extra')")
    op.execute("CREATE TYPE user_role AS ENUM ('student', 'parent', 'teacher')")

    op.add_column(
        'lessons',
        sa.Column(
            'education_level',
            sa.Enum('school', 'university', 'extra', name='education_level'),
            server_default='school',
            nullable=False,
        ),
    )
    op.add_column('lessons', sa.Column('grade_label', sa.String(length=50), nullable=True))

    op.add_column(
        'users',
        sa.Column(
            'role',
            sa.Enum('student', 'parent', 'teacher', name='user_role'),
            server_default='student',
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('users', 'role')
    op.drop_column('lessons', 'grade_label')
    op.drop_column('lessons', 'education_level')
    op.execute('DROP TYPE IF EXISTS user_role')
    op.execute('DROP TYPE IF EXISTS education_level')
