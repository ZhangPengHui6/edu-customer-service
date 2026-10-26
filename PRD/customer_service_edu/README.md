# edu-customer-service

学习机智能客服的会话 / 工单 / 维修服务（售后 MVP）。

## 技术栈

- Python 3.12、FastAPI、Pydantic v2
- SQLAlchemy 2.0（async）+ psycopg 3 + PostgreSQL
- Redis（Outbox → Pub/Sub）
- Alembic 迁移

## 目录

```text
src/edu_cs/
├─ api/            # 路由（health 已就绪，业务路由 Phase 1）
├─ models.py       # 全部 ORM 模型
├─ config.py       # 配置
├─ db.py           # async engine / session
└─ main.py         # FastAPI 入口
migrations/        # Alembic
scripts/seed.py    # 测试数据
```

## 本地启动

```bash
cd PRD/customer_service_edu
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env

alembic upgrade head
python scripts/seed.py
python scripts/dev.py --reload
```

> Windows 本地开发请用 `scripts/dev.py` 启动：psycopg 异步模式不兼容默认的 ProactorEventLoop，
> 脚本会切换到 SelectorEventLoop。Linux 上直接 `uvicorn edu_cs.main:app --port 8010` 即可。

健康检查：

- `GET http://127.0.0.1:8010/health`（存活）
- `GET http://127.0.0.1:8010/ready`（PostgreSQL + Redis 就绪）

## 数据库

- 库名：`edu_customer_service`（PostgreSQL 16.15）
- 表结构：`migrations/versions/0001_init.py`（基线，25 张表）
- 测试数据：`scripts/seed.py`（确定性 UUID，已有租户时整体跳过）

## 约定

- 所有业务表必须带 `tenant_id`；查询必须过滤租户。
- 消息 `message_id` 由客户端生成，服务端幂等。
- 单用户单渠道单开放会话：`(tenant_id, user_id, channel)` 部分唯一。
- 写操作走两阶段：AI 只准备，确认后执行。

## 配置

见 `.env.example`；密钥与真实连接信息在仓库根目录 `config.md`，不要提交。
