"""add operation_logs table

Revision ID: 20240908_000000
Revises: 17c8d77b3b72
Create Date: 2024-09-08 00:00:00.000000

新增操作日志表，记录全系统关键业务操作（登录/登出/注册/创建/更新/删除/发布/提交/导出/上传/导入）。
与 audit_logs（审核日志）独立存在。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20240908_000000'
down_revision: Union[str, Sequence[str], None] = '17c8d77b3b72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create operation_logs table."""
    op.create_table('operation_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='success', nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_operation_logs_id'), 'operation_logs', ['id'], unique=False)
    op.create_index(op.f('ix_operation_logs_user_id'), 'operation_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_operation_logs_action'), 'operation_logs', ['action'], unique=False)
    op.create_index(op.f('ix_operation_logs_created_at'), 'operation_logs', ['created_at'], unique=False)
    op.create_index('idx_operation_log_user_id', 'operation_logs', ['user_id'], unique=False)
    op.create_index('idx_operation_log_action', 'operation_logs', ['action'], unique=False)
    op.create_index('idx_operation_log_resource', 'operation_logs', ['resource_type', 'resource_id'], unique=False)
    op.create_index('idx_operation_log_created_at', 'operation_logs', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema - drop operation_logs table."""
    op.drop_index('idx_operation_log_created_at', table_name='operation_logs')
    op.drop_index('idx_operation_log_resource', table_name='operation_logs')
    op.drop_index('idx_operation_log_action', table_name='operation_logs')
    op.drop_index('idx_operation_log_user_id', table_name='operation_logs')
    op.drop_index(op.f('ix_operation_logs_created_at'), table_name='operation_logs')
    op.drop_index(op.f('ix_operation_logs_action'), table_name='operation_logs')
    op.drop_index(op.f('ix_operation_logs_user_id'), table_name='operation_logs')
    op.drop_index(op.f('ix_operation_logs_id'), table_name='operation_logs')
    op.drop_table('operation_logs')
