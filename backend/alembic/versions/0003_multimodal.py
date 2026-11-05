"""Add messages.attachments and documents.images

Revision ID: 0003_multimodal
Revises: 0002_companies_departments
Create Date: 2026-11-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0003_multimodal'
down_revision: Union[str, None] = '0002_companies_departments'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def upgrade() -> None:
    op.add_column('messages', sa.Column('attachments', _JSON, nullable=True))
    op.add_column('documents', sa.Column('images', _JSON, nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'images')
    op.drop_column('messages', 'attachments')
