"""把知识切片编码为 bge-m3 向量并写入 Milvus。

用法：
    python scripts/reindex_knowledge.py          # 只处理 pending / failed 切片
    python scripts/reindex_knowledge.py --all    # 全量重建

注意：编码是 CPU 密集的同步操作，本脚本为离线任务，直接阻塞执行。
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import select, update

from edu_ai.config import get_settings
from edu_ai.db import SessionFactory, engine
from edu_ai.knowledge import milvus_store
from edu_ai.knowledge.embedder import get_embedder
from edu_ai.models import KnowledgeArticle, KnowledgeChunk


def _epoch(value: datetime | None) -> int:
    return int(value.timestamp()) if value else 0


def _row(chunk: KnowledgeChunk, article: KnowledgeArticle, vector: list[float]) -> dict:
    return {
        "chunk_id": str(chunk.id),
        "vector": vector,
        "text": chunk.text,
        "tenant_id": str(article.tenant_id),
        "article_id": str(article.id),
        "product_model": (article.product_models or [""])[0],
        "doc_type": article.doc_type,
        "version": article.version,
        "status": article.status,
        "effective_from": _epoch(article.effective_from),
        "effective_to": _epoch(article.effective_to),
        "chunk_index": chunk.chunk_index,
        "source_title": article.title,
    }


async def reindex(all_chunks: bool) -> None:
    settings = get_settings()
    embedder = get_embedder()

    async with SessionFactory() as session:
        stmt = (
            select(KnowledgeChunk, KnowledgeArticle)
            .join(KnowledgeArticle, KnowledgeChunk.article_id == KnowledgeArticle.id)
            .where(KnowledgeArticle.status == "published")
            .order_by(KnowledgeChunk.article_id, KnowledgeChunk.chunk_index)
        )
        if not all_chunks:
            stmt = stmt.where(KnowledgeChunk.vector_status.in_(("pending", "failed")))

        rows = (await session.execute(stmt)).all()
        if not rows:
            print("没有需要重建的切片。")
            return

        by_article: dict[UUID, list[tuple[KnowledgeChunk, KnowledgeArticle]]] = defaultdict(list)
        for chunk, article in rows:
            by_article[article.id].append((chunk, article))

        total = 0
        for article_id, pairs in by_article.items():
            article = pairs[0][1]
            texts = [chunk.text for chunk, _ in pairs]
            try:
                vectors = embedder.embed_documents(texts)
                if vectors and len(vectors[0]) != settings.embedding_dimension:
                    raise RuntimeError(
                        f"向量维度 {len(vectors[0])} 与配置 {settings.embedding_dimension} 不一致"
                    )

                # 先删旧向量，避免文章修订后留下失效切片。
                milvus_store.delete_by_article(str(article_id))
                milvus_store.upsert_chunks(
                    [
                        _row(chunk, pair_article, vector)
                        for (chunk, pair_article), vector in zip(pairs, vectors, strict=True)
                    ]
                )

                await session.execute(
                    update(KnowledgeChunk)
                    .where(KnowledgeChunk.id.in_([chunk.id for chunk, _ in pairs]))
                    .values(
                        vector_status="indexed",
                        indexed_at=datetime.now(UTC),
                    )
                )
                await session.commit()
                total += len(pairs)
                print(f"  {article.slug}: {len(pairs)} 切片")
            except Exception as exc:  # noqa: BLE001 - 单篇失败不阻断其余文章
                await session.rollback()
                await session.execute(
                    update(KnowledgeChunk)
                    .where(KnowledgeChunk.id.in_([chunk.id for chunk, _ in pairs]))
                    .values(vector_status="failed")
                )
                await session.commit()
                print(f"  {article.slug}: 失败 - {type(exc).__name__}: {exc}")

    print(f"重建完成：{total} 个切片写入 Milvus。")


async def main() -> None:
    try:
        await reindex(all_chunks="--all" in sys.argv[1:])
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
