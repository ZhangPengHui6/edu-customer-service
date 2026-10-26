FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
ARG INSTALL_EMBEDDING=false
RUN pip install . \
    && if [ "$INSTALL_EMBEDDING" = "true" ]; then pip install "sentence-transformers>=3.0.0"; fi

COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts

EXPOSE 8002

# bge-m3 与 sentence-transformers 不打进镜像；知识重建在宿主机或独立任务中执行。
CMD ["uvicorn", "edu_ai.main:app", "--host", "0.0.0.0", "--port", "8002"]
