"""Phase 0 基线：按 ORM 元数据建表。

Revision ID: 0001
Revises:
Create Date: 2026-10-26

"""

from alembic import op

from edu_ai.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
