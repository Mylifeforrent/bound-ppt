"""Initial schema for Bound PPT M1.

Revision ID: 0001_initial
Revises: None
Create Date: 2026-11-19

The metadata is the single schema source; this initial migration materializes it.
Subsequent schema changes MUST be generated with
`alembic revision --autogenerate -m "<change>"` against PostgreSQL.
"""

from __future__ import annotations

from alembic import op

from app.models import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
