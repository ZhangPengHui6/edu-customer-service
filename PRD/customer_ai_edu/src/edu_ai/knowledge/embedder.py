"""bge-m3 本地向量化。

模型延迟加载：健康检查、迁移等命令不会占用内存。
"""

from __future__ import annotations

from functools import lru_cache
from threading import Lock

from edu_ai.config import get_settings


class BGEM3Embedder:
    def __init__(self, model_path: str, device: str = "cpu", batch_size: int = 16) -> None:
        self.model_path = model_path
        self.device = device
        self.batch_size = batch_size
        self._model = None
        self._load_lock = Lock()
        self._encode_lock = Lock()

    def _ensure_model(self):
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                    except ImportError as exc:  # pragma: no cover - 环境相关
                        raise RuntimeError(
                            "未安装 sentence-transformers，请使用 pip install -e '.[embedding]'"
                        ) from exc
                    # 默认 low_cpu_mem_usage=True 会先建 meta tensor，再 .to(device)
                    # 在部分 torch 版本上会报 "Cannot copy out of meta tensor"。
                    self._model = SentenceTransformer(
                        self.model_path,
                        device=self.device,
                        model_kwargs={"low_cpu_mem_usage": False},
                    )
        return self._model

    @property
    def dimension(self) -> int:
        return int(self._ensure_model().get_sentence_embedding_dimension())

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        with self._encode_lock:
            vectors = self._ensure_model().encode(
                texts,
                batch_size=self.batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


@lru_cache
def get_embedder() -> BGEM3Embedder:
    settings = get_settings()
    embedder = BGEM3Embedder(
        model_path=settings.embedding_model_path,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
    )
    # 首次真实编码时再校验维度，避免启动即加载模型。
    return embedder
