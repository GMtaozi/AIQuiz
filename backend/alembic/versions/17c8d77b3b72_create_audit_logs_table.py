"""create audit_logs table

Revision ID: 17c8d77b3b72
Revises: c3b53d81ed6e
Create Date: 2026-08-13 00:00:00.000000

修复评估发现：models/question.py 定义了 AuditLog（__tablename__="audit_logs"），
但此前没有任何迁移创建该表，导致 Alembic 管理的数据库上审核功能必然报错
（relation "audit_logs" does not exist）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '17c8d77b3b72'
down_revision: Union[str, Sequence[str], None] = 'c3b53d81ed6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create audit_logs table (matches models/question.py AuditLog)."""
    op.create_table('audit_logs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.Column('auditor_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=20), nullable=False),
    sa.Column('old_status', sa.String(length=20), nullable=True),
    sa.Column('new_status', sa.String(length=20), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('ip_address', sa.String(length=50), nullable=True),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['auditor_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_auditor_id'), 'audit_logs', ['auditor_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_question_id'), 'audit_logs', ['question_id'], unique=False)
    op.create_index('idx_audit_log_auditor_id', 'audit_logs', ['auditor_id'], unique=False)
    op.create_index('idx_audit_log_question_id', 'audit_logs', ['question_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema - drop audit_logs table."""
    op.drop_index('idx_audit_log_question_id', table_name='audit_logs')
    op.drop_index('idx_audit_log_auditor_id', table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_question_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_auditor_id'), table_name='audit_logs')
    op.drop_table('audit_logs')
