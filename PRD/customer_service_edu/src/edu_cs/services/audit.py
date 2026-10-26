"""审计日志。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from edu_cs.models import AuditLog


async def record(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_id: UUID | None,
    action: str,
    object_type: str,
    object_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        before=before,
        after=after,
    )
    session.add(entry)
    await session.flush()
    return entry
