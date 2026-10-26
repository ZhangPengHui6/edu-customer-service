"""知识检索：bge-m3 向量 + Milvus 标量过滤。"""

from __future__ import annotations

import asyncio
from uuid import NAMESPACE_URL, UUID, uuid5

from edu_ai.agent.tools.result import KnowledgeHit
from edu_ai.config import get_settings
from edu_ai.knowledge import milvus_store
from edu_ai.knowledge.embedder import get_embedder

_SEED_NAMESPACE = uuid5(NAMESPACE_URL, "https://edu-cs.local/seed")
HQ_TENANT_ID = uuid5(_SEED_NAMESPACE, "tenant:hq")


def hq_tenant_id() -> UUID:
    return HQ_TENANT_ID


class KnowledgeService:
    """只读知识检索；tenant 范围 = 当前租户 + 总部 all_dealers 内容。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def search(self, query: str, tenant_id: str) -> list[KnowledgeHit]:
        normalized = query.strip()
        if not normalized:
            return []

        tenant_ids = [tenant_id]
        if tenant_id != str(HQ_TENANT_ID):
            tenant_ids.append(str(HQ_TENANT_ID))

        vector = await asyncio.to_thread(
            get_embedder().embed_query, normalized
        )
        hits = await asyncio.to_thread(
            milvus_store.search,
            vector,
            tenant_ids,
            self.settings.retrieval_top_k,
        )
        return [
            KnowledgeHit(**hit)
            for hit in hits
            if hit.get("score", 0.0) >= self.settings.retrieval_score_threshold
        ]


knowledge_service = KnowledgeService()
