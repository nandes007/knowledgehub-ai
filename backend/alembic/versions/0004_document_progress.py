"""Add documents.progress

Revision ID: 0004_document_progress
Revises: 0003_multimodal
Create Date: 2026-11-09 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004_document_progress'
down_revision: Union[str, None] = '0003_multimodal'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('progress', sa.Integer(), nullable=False, server_default='0'))
    # Rows that already finished ingesting show a full bar.
    op.execute("UPDATE documents SET progress = 100 WHERE status = 'ready'")


def downgrade() -> None:
    op.drop_column('documents', 'progress')
