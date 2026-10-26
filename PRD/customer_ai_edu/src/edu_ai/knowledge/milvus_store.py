"""Milvus collection 封装。

Phase 0 建 dense 向量字段与标量过滤字段；BM25 稀疏检索在 Phase 1 第二周加入
（复用同一 collection 的 text 字段 + 全文索引），此处不启用。

当前使用 pymilvus 的 ORM 风格 API（与 Milvus 2.5.5 匹配）；升级到 Milvus 3.x 前
需迁移到 MilvusClient。
"""

from __future__ import annotations

from functools import lru_cache

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from edu_ai.config import get_settings

ALIAS = "edu_ai"


def _field(name: str, dtype: DataType, **kwargs) -> FieldSchema:
    return FieldSchema(name=name, dtype=dtype, **kwargs)


@lru_cache
def get_collection() -> Collection:
    settings = get_settings()
    connections.connect(
        alias=ALIAS,
        uri=settings.milvus_uri,
        token=settings.milvus_token or "",
    )

    if utility.has_collection(settings.milvus_collection, using=ALIAS):
        return Collection(settings.milvus_collection, using=ALIAS)

    schema = CollectionSchema(
        fields=[
            _field("chunk_id", DataType.VARCHAR, is_primary=True, max_length=64),
            _field("vector", DataType.FLOAT_VECTOR, dim=settings.embedding_dimension),
            _field("text", DataType.VARCHAR, max_length=16384),
            _field("tenant_id", DataType.VARCHAR, max_length=64),
            _field("article_id", DataType.VARCHAR, max_length=64),
            _field("product_model", DataType.VARCHAR, max_length=64),
            _field("doc_type", DataType.VARCHAR, max_length=32),
            _field("version", DataType.INT64),
            _field("status", DataType.VARCHAR, max_length=16),
            _field("effective_from", DataType.INT64),
            _field("effective_to", DataType.INT64),
            _field("chunk_index", DataType.INT64),
            _field("source_title", DataType.VARCHAR, max_length=512),
        ],
        description="学习机客服知识库 chunk 向量",
        enable_dynamic_field=False,
    )
    collection = Collection(settings.milvus_collection, schema=schema, using=ALIAS)

    collection.create_index(
        field_name="vector",
        index_params={"index_type": "AUTOINDEX", "metric_type": "COSINE"},
    )
    for name in ("tenant_id", "article_id", "product_model", "doc_type", "status"):
        collection.create_index(field_name=name, index_params={"index_type": "INVERTED"})

    return collection


def _loaded_collection() -> Collection:
    """Milvus 的 upsert/delete 同样要求集合已加载，否则报 collection not loaded。"""
    collection = get_collection()
    collection.load()
    return collection


def upsert_chunks(rows: list[dict]) -> int:
    if not rows:
        return 0
    collection = _loaded_collection()
    collection.upsert(rows)
    collection.flush()
    return len(rows)


def delete_by_article(article_id: str) -> None:
    collection = _loaded_collection()
    collection.delete(expr=f"article_id == {_quote(article_id)}")
    collection.flush()


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def search(
    vector: list[float],
    tenant_ids: list[str],
    top_k: int = 6,
    doc_type: str | None = None,
) -> list[dict]:
    if not tenant_ids:
        return []

    collection = get_collection()
    collection.load()

    quoted = ", ".join(_quote(item) for item in tenant_ids)
    expr = f"tenant_id in [{quoted}] and status == 'published'"
    if doc_type:
        expr += f" and doc_type == {_quote(doc_type)}"

    results = collection.search(
        data=[vector],
        anns_field="vector",
        param={"metric_type": "COSINE", "params": {}},
        limit=top_k,
        expr=expr,
        output_fields=[
            "text",
            "article_id",
            "chunk_index",
            "source_title",
            "doc_type",
            "version",
        ],
    )

    hits: list[dict] = []
    for hit in results[0]:
        hits.append(
            {
                "chunk_id": hit.id,
                "score": hit.score,
                "text": hit.entity.get("text", ""),
                "article_id": hit.entity.get("article_id"),
                "chunk_index": hit.entity.get("chunk_index"),
                "source_title": hit.entity.get("source_title"),
                "doc_type": hit.entity.get("doc_type"),
                "version": hit.entity.get("version"),
            }
        )
    return hits
