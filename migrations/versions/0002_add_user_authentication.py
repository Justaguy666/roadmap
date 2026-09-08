"""add_user_authentication

Revision ID: 0002_add_user_auth
Revises: 94579f682a90
Create Date: 2026-09-08 07:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0002_add_user_auth'
down_revision: str | None = '94579f682a90'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_USER_ID = "legacy-local-user-000000000000"
LEGACY_USER_EMAIL = "local@roadmap.ai"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Create users table if not exists
    if 'users' not in tables:
        op.create_table(
            'users',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
        )
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    # Re-inspect to confirm tables
    inspector = sa.inspect(bind)
    cols = [c['name'] for c in inspector.get_columns('user_profiles')]

    # 2. Add user_id to user_profiles with deterministic legacy bootstrap
    if 'user_id' not in cols:
        now = datetime.now(UTC)
        # Check if legacy profiles exist
        profile_count = bind.execute(sa.text("SELECT COUNT(*) FROM user_profiles")).scalar() or 0
        if profile_count > 0:
            user_exists = bind.execute(
                sa.text("SELECT COUNT(*) FROM users WHERE id = :uid"),
                {"uid": LEGACY_USER_ID},
            ).scalar() or 0
            if user_exists == 0:
                bind.execute(
                    sa.text(
                        "INSERT INTO users (id, email, password_hash, status, created_at, updated_at) "
                        "VALUES (:id, :email, :pw, :status, :created, :updated)"
                    ),
                    {
                        "id": LEGACY_USER_ID,
                        "email": LEGACY_USER_EMAIL,
                        "pw": "$2b$12$e898492049182390182390e898492049182390182390e89849204",
                        "status": "active",
                        "created": now,
                        "updated": now,
                    },
                )

        with op.batch_alter_table('user_profiles', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    'user_id',
                    sa.String(length=36),
                    nullable=False,
                    server_default=LEGACY_USER_ID,
                )
            )
            batch_op.create_foreign_key(
                batch_op.f('fk_user_profiles_user_id_users'),
                'users',
                ['user_id'],
                ['id'],
                ondelete='CASCADE',
            )
            batch_op.create_index(
                batch_op.f('ix_user_profiles_user_id'),
                ['user_id'],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c['name'] for c in inspector.get_columns('user_profiles')]

    if 'user_id' in cols:
        with op.batch_alter_table('user_profiles', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_user_profiles_user_id'))
            batch_op.drop_constraint(batch_op.f('fk_user_profiles_user_id_users'), type_='foreignkey')
            batch_op.drop_column('user_id')

    tables = inspector.get_table_names()
    if 'users' in tables:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_users_email'))
        op.drop_table('users')
