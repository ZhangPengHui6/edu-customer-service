"""Phase 0 基线：按 ORM 元数据建表。

首个迁移直接使用 `Base.metadata` 建全量结构，保证模型与库一致；
从 0002 起用 `alembic revision --autogenerate` 生成增量迁移。

Revision ID: 0001
Revises:
Create Date: 2026-10-26

"""

from alembic import op

from edu_cs.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
