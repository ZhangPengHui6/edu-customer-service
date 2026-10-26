# 部署说明（Phase 0）

目标机 `192.168.168.100` 已安装 PostgreSQL / Redis / Milvus / MinIO，Compose 只编排两个业务服务。

## 1. 建库（一次性）

```bash
psql -h 192.168.168.100 -U postgres -f init/00_create_databases.sql
```

脚本创建 `customer_service` 角色（若不存在）与 `edu_customer_service`、`edu_ai_service` 两个库。
生产环境请改掉默认密码，并收紧 `pg_hba.conf`。

## 2. 配置

```bash
cp .env.example .env
# 填入 DASHSCOPE_API_KEY，按需改 INTERNAL_SERVICE_TOKEN / JWT_SECRET
```

`INTERNAL_SERVICE_TOKEN` 与 `JWT_SECRET` 必须两个服务一致；`DASHSCOPE_API_KEY` 不要提交到仓库。

## 3. 启动

```bash
docker compose up -d --build
docker compose ps
```

## 4. 迁移与测试数据

```bash
docker compose exec customer-service alembic upgrade head
docker compose exec customer-service python scripts/seed.py

docker compose exec ai-service alembic upgrade head
docker compose exec ai-service python scripts/seed_knowledge.py
```

两个 seed 都是幂等的：检测到已有数据就跳过，不会重复插入。

## 5. 知识向量化

默认镜像不含 `sentence-transformers`（torch 体积大）。二选一：

- 在宿主机装依赖后跑：`python scripts/reindex_knowledge.py`
- 或用带 embedding 的镜像：

```bash
INSTALL_EMBEDDING=true EMBEDDING_HOST_DIR=/opt/models/bge-m3 docker compose build ai-service
docker compose up -d ai-service
docker compose exec ai-service python scripts/reindex_knowledge.py
```

`bge-m3` 目录需提前放到宿主机 `EMBEDDING_HOST_DIR`（默认 `/opt/models/bge-m3`）。

## 6. 验证

```bash
curl -s http://192.168.168.100:8000/health
curl -s http://192.168.168.100:8002/health
curl -s http://192.168.168.100:8000/ready
curl -s http://192.168.168.100:8002/ready
```

`/ready` 返回 503 时看 `checks` 字段，常见原因是 PostgreSQL 口令或 Milvus `9091/healthz` 不可达。

## 7. 备注

- 容器通过 `192.168.168.100` 访问宿主机上的 PG / Redis / Milvus，不要写成 `127.0.0.1`。
- 本轮不包含 Nginx / TLS / 域名；Phase 1 接入统一网关时再加。
- 日志走 json-file，已限制单文件 20MB、最多 5 个。
