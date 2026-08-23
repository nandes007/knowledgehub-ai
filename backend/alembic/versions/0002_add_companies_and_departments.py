"""Add companies, departments, and tenant scoping to users, documents, conversations

Revision ID: 0002_add_companies_and_departments
Revises: 0001_initial_schema
Create Date: 2026-08-23 10:30:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_add_companies_and_departments'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create companies table
    op.create_table(
        'companies',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('status', sa.String(), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('active', 'suspended')", name='ck_companies_status'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_companies_name'), 'companies', ['name'], unique=True)

    # 2. Create departments table
    op.create_table(
        'departments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'name', name='uq_departments_company_name'),
    )
    op.create_index('idx_departments_company', 'departments', ['company_id'], unique=False)

    # 3. Add columns to users
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('company_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('department_id', sa.Uuid(), nullable=True))
        batch_op.add_column(
            sa.Column('approval_status', sa.String(), server_default='pending', nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_users_company_id', 'companies', ['company_id'], ['id'], ondelete='CASCADE'
        )
        batch_op.create_foreign_key(
            'fk_users_department_id', 'departments', ['department_id'], ['id'], ondelete='SET NULL'
        )
        batch_op.create_check_constraint(
            'ck_users_role', "role IN ('superadmin', 'admin', 'member')"
        )
        batch_op.create_check_constraint(
            'ck_users_approval_status', "approval_status IN ('pending', 'approved', 'rejected')"
        )
        batch_op.create_index('idx_users_company', ['company_id'], unique=False)

    # 4. Add columns to documents
    with op.batch_alter_table('documents') as batch_op:
        batch_op.add_column(sa.Column('company_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('uploaded_by', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('department_id', sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            'fk_documents_company_id', 'companies', ['company_id'], ['id'], ondelete='CASCADE'
        )
        batch_op.create_foreign_key(
            'fk_documents_uploaded_by', 'users', ['uploaded_by'], ['id'], ondelete='CASCADE'
        )
        batch_op.create_foreign_key(
            'fk_documents_department_id', 'departments', ['department_id'], ['id'], ondelete='SET NULL'
        )
        batch_op.create_index('idx_documents_company', ['company_id', 'created_at'], unique=False)
        batch_op.create_index('idx_documents_uploaded_by', ['uploaded_by', 'created_at'], unique=False)

    # 5. Add columns to conversations
    with op.batch_alter_table('conversations') as batch_op:
        batch_op.add_column(sa.Column('company_id', sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            'fk_conversations_company_id', 'companies', ['company_id'], ['id'], ondelete='CASCADE'
        )
        batch_op.create_index('idx_conversations_company', ['company_id', 'updated_at'], unique=False)

    # 6. Backfill existing data
    bind = op.get_bind()

    companies_table = sa.table(
        'companies',
        sa.column('id', sa.Uuid()),
        sa.column('name', sa.String()),
        sa.column('status', sa.String()),
        sa.column('created_at', sa.DateTime(timezone=True)),
        sa.column('updated_at', sa.DateTime(timezone=True)),
    )
    users_table = sa.table(
        'users',
        sa.column('id', sa.Uuid()),
        sa.column('company_id', sa.Uuid()),
        sa.column('role', sa.String()),
        sa.column('approval_status', sa.String()),
    )
    documents_table = sa.table(
        'documents',
        sa.column('id', sa.Uuid()),
        sa.column('user_id', sa.Uuid()),
        sa.column('uploaded_by', sa.Uuid()),
        sa.column('company_id', sa.Uuid()),
    )
    conversations_table = sa.table(
        'conversations',
        sa.column('id', sa.Uuid()),
        sa.column('company_id', sa.Uuid()),
    )

    user_rows = bind.execute(sa.select(users_table.c.id)).fetchall()
    if user_rows:
        default_company_id = uuid.uuid4()
        now_dt = datetime.now(timezone.utc)
        bind.execute(
            sa.insert(companies_table).values(
                id=default_company_id,
                name="Nandes Tech",
                status="active",
                created_at=now_dt,
                updated_at=now_dt,
            )
        )

        # Backfill users
        bind.execute(
            sa.update(users_table)
            .where(users_table.c.company_id.is_(None))
            .values(company_id=default_company_id, role="admin", approval_status="approved")
        )

        # Backfill documents (uploaded_by = user_id, company_id = default_company_id)
        bind.execute(
            sa.update(documents_table)
            .where(documents_table.c.company_id.is_(None))
            .values(company_id=default_company_id, uploaded_by=documents_table.c.user_id)
        )

        # Backfill conversations
        bind.execute(
            sa.update(conversations_table)
            .where(conversations_table.c.company_id.is_(None))
            .values(company_id=default_company_id)
        )

    # 7. Finalize schema (drop deprecated columns, enforce non-null)
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('department')
        batch_op.alter_column('approval_status', nullable=False)

    with op.batch_alter_table('documents') as batch_op:
        batch_op.drop_index('idx_documents_user')
        batch_op.drop_column('department')
        batch_op.drop_column('user_id')
        batch_op.alter_column('company_id', nullable=False)
        batch_op.alter_column('uploaded_by', nullable=False)

    with op.batch_alter_table('conversations') as batch_op:
        batch_op.alter_column('company_id', nullable=False)


def downgrade() -> None:
    # 1. Restore documents schema
    with op.batch_alter_table('documents') as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('department', sa.String(), nullable=True))

    documents_table = sa.table(
        'documents',
        sa.column('id', sa.Uuid()),
        sa.column('user_id', sa.Uuid()),
        sa.column('uploaded_by', sa.Uuid()),
    )
    bind = op.get_bind()
    bind.execute(
        sa.update(documents_table)
        .where(documents_table.c.user_id.is_(None))
        .values(user_id=documents_table.c.uploaded_by)
    )

    with op.batch_alter_table('documents') as batch_op:
        batch_op.alter_column('user_id', nullable=False)
        batch_op.create_foreign_key(
            'fk_documents_user_id', 'users', ['user_id'], ['id'], ondelete='CASCADE'
        )
        batch_op.create_index('idx_documents_user', ['user_id', 'created_at'], unique=False)
        batch_op.drop_index('idx_documents_uploaded_by')
        batch_op.drop_index('idx_documents_company')
        batch_op.drop_constraint('fk_documents_company_id', type_='foreignkey')
        batch_op.drop_constraint('fk_documents_uploaded_by', type_='foreignkey')
        batch_op.drop_constraint('fk_documents_department_id', type_='foreignkey')
        batch_op.drop_column('department_id')
        batch_op.drop_column('uploaded_by')
        batch_op.drop_column('company_id')

    # 2. Restore conversations schema
    with op.batch_alter_table('conversations') as batch_op:
        batch_op.drop_index('idx_conversations_company')
        batch_op.drop_constraint('fk_conversations_company_id', type_='foreignkey')
        batch_op.drop_column('company_id')

    # 3. Restore users schema
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('department', sa.String(), nullable=True))
        batch_op.drop_index('idx_users_company')
        batch_op.drop_constraint('ck_users_role', type_='check')
        batch_op.drop_constraint('ck_users_approval_status', type_='check')
        batch_op.drop_constraint('fk_users_company_id', type_='foreignkey')
        batch_op.drop_constraint('fk_users_department_id', type_='foreignkey')
        batch_op.drop_column('approval_status')
        batch_op.drop_column('department_id')
        batch_op.drop_column('company_id')

    # 4. Drop departments table
    op.drop_index('idx_departments_company', table_name='departments')
    op.drop_table('departments')

    # 5. Drop companies table
    op.drop_index(op.f('ix_companies_name'), table_name='companies')
    op.drop_table('companies')
