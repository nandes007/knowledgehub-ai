"""Initial baseline schema migration

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-08-06 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=True),
        sa.Column('role', sa.String(), server_default='member', nullable=False),
        sa.Column('department', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. documents table
    op.create_table(
        'documents',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('content_type', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('file_hash', sa.String(), nullable=False),
        sa.Column('status', sa.String(), server_default='processing', nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('doc_type', sa.String(), server_default='general', nullable=False),
        sa.Column('department', sa.String(), nullable=True),
        sa.Column('visibility', sa.String(), server_default='company', nullable=False),
        sa.Column('chunk_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('processing', 'ready', 'failed')", name='ck_documents_status'),
        sa.CheckConstraint("visibility IN ('company', 'department')", name='ck_documents_visibility'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_documents_status', 'documents', ['status'], unique=False)
    op.create_index('idx_documents_user', 'documents', ['user_id', 'created_at'], unique=False)

    # 3. conversations table
    op.create_table(
        'conversations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(), server_default='New chat', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_conversations_user', 'conversations', ['user_id', 'updated_at'], unique=False)

    # 4. messages table
    json_type = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')
    op.create_table(
        'messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('conversation_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('sources', json_type, nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name='ck_messages_role'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_messages_conversation', 'messages', ['conversation_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_messages_conversation', table_name='messages')
    op.drop_table('messages')

    op.drop_index('idx_conversations_user', table_name='conversations')
    op.drop_table('conversations')

    op.drop_index('idx_documents_user', table_name='documents')
    op.drop_index('idx_documents_status', table_name='documents')
    op.drop_table('documents')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
