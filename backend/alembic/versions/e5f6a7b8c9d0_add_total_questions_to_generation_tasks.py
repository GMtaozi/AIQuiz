"""add total_questions to generation_tasks

Revision ID: e5f6a7b8c9d0
Revises: 17c8d77b3b72
Create Date: 2026-08-13 00:00:00.000000

修复评估发现：models/question.py 的 GenerationTask 在 tasks.py 中被读写
total_questions 字段（任务进度接口），但表中无此列，导致访问进度接口 500。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = '17c8d77b3b72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add total_questions column with server default for existing rows."""
    with op.batch_alter_table('generation_tasks') as batch_op:
        batch_op.add_column(
            sa.Column('total_questions', sa.Integer(), server_default='0', nullable=False)
        )


def downgrade() -> None:
    """Downgrade schema - drop total_questions column."""
    with op.batch_alter_table('generation_tasks') as batch_op:
        batch_op.drop_column('total_questions')
