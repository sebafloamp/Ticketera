"""add reminder_day to users

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('reminder_day', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'reminder_day')
