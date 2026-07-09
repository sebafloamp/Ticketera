"""periodos conjuntos: is_joint + period_participants + ticket_assignees

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'periods',
        sa.Column('is_joint', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        'period_participants',
        sa.Column('period_id', sa.Integer(), sa.ForeignKey('periods.id'), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), primary_key=True),
    )
    op.create_table(
        'ticket_assignees',
        sa.Column('ticket_id', sa.Integer(), sa.ForeignKey('tickets.id'), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table('ticket_assignees')
    op.drop_table('period_participants')
    op.drop_column('periods', 'is_joint')
