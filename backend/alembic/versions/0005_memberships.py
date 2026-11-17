"""Multi-tenant RBAC: memberships, invites, company slugs, instance admins

Users become global accounts. Their company, role and department move onto a
membership row, 'superadmin' becomes the is_instance_admin flag, and each company
gets a URL slug and exactly one owner.

Revision ID: 0005_memberships
Revises: 0004_document_progress
Create Date: 2026-11-17 10:00:00.000000

"""
import re
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_memberships'
down_revision: Union[str, None] = '0004_document_progress'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Copied from app.services.companies: a migration must not change when the app does.
_RESERVED_SLUGS = {"login", "register", "invite", "instance", "new", "api", "admin"}

companies_t = sa.table(
    'companies',
    sa.column('id', sa.Uuid()),
    sa.column('name', sa.String()),
    sa.column('slug', sa.String()),
    sa.column('created_at', sa.DateTime(timezone=True)),
)
users_t = sa.table(
    'users',
    sa.column('id', sa.Uuid()),
    sa.column('company_id', sa.Uuid()),
    sa.column('department_id', sa.Uuid()),
    sa.column('role', sa.String()),
    sa.column('is_instance_admin', sa.Boolean()),
    sa.column('created_at', sa.DateTime(timezone=True)),
)
memberships_t = sa.table(
    'memberships',
    sa.column('id', sa.Uuid()),
    sa.column('user_id', sa.Uuid()),
    sa.column('company_id', sa.Uuid()),
    sa.column('role', sa.String()),
    sa.column('department_id', sa.Uuid()),
    sa.column('created_at', sa.DateTime(timezone=True)),
)


def _slug(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48].strip("-") or "company"
    slug, n = base, 1
    while slug in taken or slug in _RESERVED_SLUGS:
        n += 1
        slug = f"{base}-{n}"
    taken.add(slug)
    return slug


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Company slugs, generated from the (unique) names.
    op.add_column('companies', sa.Column('slug', sa.String(), nullable=True))
    taken: set[str] = set()
    for company in bind.execute(sa.select(companies_t.c.id, companies_t.c.name).order_by(companies_t.c.created_at)):
        bind.execute(
            sa.update(companies_t).where(companies_t.c.id == company.id).values(slug=_slug(company.name, taken))
        )
    with op.batch_alter_table('companies') as batch_op:
        batch_op.alter_column('slug', existing_type=sa.String(), nullable=False)
    op.create_index(op.f('ix_companies_slug'), 'companies', ['slug'], unique=True)

    # 2. Superadmins become instance admins.
    op.add_column(
        'users', sa.Column('is_instance_admin', sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    bind.execute(sa.update(users_t).where(users_t.c.role == 'superadmin').values(is_instance_admin=True))

    # 3. Memberships and invites.
    op.create_table(
        'memberships',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('department_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member')", name='ck_memberships_role'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'company_id', name='uq_memberships_user_company'),
    )
    op.create_index('idx_memberships_company', 'memberships', ['company_id'], unique=False)

    op.create_table(
        'invites',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('department_id', sa.Uuid(), nullable=True),
        sa.Column('invited_by', sa.Uuid(), nullable=False),
        sa.Column('token_hash', sa.String(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'member')", name='ck_invites_role'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_invites_company', 'invites', ['company_id'], unique=False)
    op.create_index(op.f('ix_invites_email'), 'invites', ['email'], unique=False)
    op.create_index(op.f('ix_invites_token_hash'), 'invites', ['token_hash'], unique=True)

    # 4. One membership per user who had a company. The earliest admin of each company
    #    becomes its owner (the earliest member, if it somehow has no admin), so every
    #    company with people in it has exactly one owner.
    members = bind.execute(
        sa.select(
            users_t.c.id, users_t.c.company_id, users_t.c.department_id, users_t.c.role, users_t.c.created_at
        )
        .where(users_t.c.company_id.is_not(None))
        .order_by(users_t.c.created_at, users_t.c.id)
    ).fetchall()
    owners: dict = {}
    for user in members:
        current = owners.get(user.company_id)
        if current is None or (user.role == 'admin' and current.role != 'admin'):
            owners[user.company_id] = user
    if members:
        bind.execute(
            sa.insert(memberships_t),
            [
                {
                    'id': uuid.uuid4(),
                    'user_id': user.id,
                    'company_id': user.company_id,
                    'role': (
                        'owner'
                        if owners[user.company_id].id == user.id
                        else 'admin' if user.role == 'admin' else 'member'
                    ),
                    'department_id': user.department_id,
                    'created_at': user.created_at,
                }
                for user in members
            ],
        )

    # After the backfill, so a bad backfill fails here rather than passing silently.
    op.create_index(
        'uq_memberships_company_owner',
        'memberships',
        ['company_id'],
        unique=True,
        postgresql_where=sa.text("role = 'owner'"),
        sqlite_where=sa.text("role = 'owner'"),
    )

    # 5. The user row no longer says anything about companies.
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_index('idx_users_company')
        batch_op.drop_constraint('ck_users_role', type_='check')
        batch_op.drop_constraint('fk_users_company_id', type_='foreignkey')
        batch_op.drop_constraint('fk_users_department_id', type_='foreignkey')
        batch_op.drop_column('role')
        batch_op.drop_column('department_id')
        batch_op.drop_column('company_id')


def downgrade() -> None:
    """Lossy: a user in several companies keeps only the one they joined first, and
    owners go back to being admins."""
    bind = op.get_bind()

    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('company_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('department_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('role', sa.String(), server_default='member', nullable=False))

    seen: set = set()
    for membership in bind.execute(
        sa.select(
            memberships_t.c.user_id, memberships_t.c.company_id, memberships_t.c.department_id, memberships_t.c.role
        ).order_by(memberships_t.c.created_at)
    ).fetchall():
        if membership.user_id in seen:
            continue
        seen.add(membership.user_id)
        bind.execute(
            sa.update(users_t)
            .where(users_t.c.id == membership.user_id)
            .values(
                company_id=membership.company_id,
                department_id=membership.department_id,
                role='member' if membership.role == 'member' else 'admin',
            )
        )
    bind.execute(sa.update(users_t).where(users_t.c.is_instance_admin.is_(True)).values(role='superadmin'))

    with op.batch_alter_table('users') as batch_op:
        batch_op.create_foreign_key(
            'fk_users_company_id', 'companies', ['company_id'], ['id'], ondelete='CASCADE'
        )
        batch_op.create_foreign_key(
            'fk_users_department_id', 'departments', ['department_id'], ['id'], ondelete='SET NULL'
        )
        batch_op.create_check_constraint('ck_users_role', "role IN ('superadmin', 'admin', 'member')")
        batch_op.create_index('idx_users_company', ['company_id'], unique=False)
        batch_op.drop_column('is_instance_admin')

    op.drop_index(op.f('ix_invites_token_hash'), table_name='invites')
    op.drop_index(op.f('ix_invites_email'), table_name='invites')
    op.drop_index('idx_invites_company', table_name='invites')
    op.drop_table('invites')

    op.drop_index('uq_memberships_company_owner', table_name='memberships')
    op.drop_index('idx_memberships_company', table_name='memberships')
    op.drop_table('memberships')

    op.drop_index(op.f('ix_companies_slug'), table_name='companies')
    with op.batch_alter_table('companies') as batch_op:
        batch_op.drop_column('slug')
