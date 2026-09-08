"""add graded_by and graded_at to user_answers

Revision ID: 20240909_000000
Revises: 20240908_000000
Create Date: 2024-09-09 00:00:00.000000

新增 graded_by 和 graded_at 字段到 user_answers 表，用于记录主观题的批改人和批改时间。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20240909_000000'
down_revision: Union[str, Sequence[str], None] = '20240908_000000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add graded_by and graded_at to user_answers."""
    op.add_column('user_answers', sa.Column('graded_by', sa.Integer(), nullable=True))
    op.add_column('user_answers', sa.Column('graded_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key('fk_user_answers_graded_by', 'user_answers', 'users', ['graded_by'], ['id'])
    op.create_index(op.f('ix_user_answers_graded_by'), 'user_answers', ['graded_by'], unique=False)


def downgrade() -> None:
    """Downgrade schema - remove graded_by and graded_at from user_answers."""
    op.drop_index(op.f('ix_user_answers_graded_by'), table_name='user_answers')
    op.drop_constraint('fk_user_answers_graded_by', 'user_answers', type_='foreignkey')
    op.drop_column('user_answers', 'graded_at')
    op.drop_column('user_answers', 'graded_by')
