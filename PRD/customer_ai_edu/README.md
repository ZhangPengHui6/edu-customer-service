# edu-ai-service

学习机智能客服的 AI 服务：Agent 编排、技能、工具、知识检索与评测。

## 技术栈

- Python 3.12 / FastAPI
- LangChain 1.x（`create_agent` + 自定义 state/context）
- PostgreSQL 16.15（元数据、AgentRun、知识切片索引）
- Milvus 2.5.5（dense 向量；BM25 在 Phase 1 第二周加入）
- bge-m3（本地 1024 维，`sentence-transformers` 可选依赖）
- 七牛云 OpenAI 兼容网关（多模型路由）

## 目录

```
src/edu_ai/
├── api/            # 内部 HTTP 接口（/internal/v1）
├── agent/          # create_agent、技能、工具、输出校验
├── knowledge/      # embedder / milvus_store / 切分
├── schemas/        # Pydantic 模型
├── repositories/   # 数据访问
├── services/       # 编排
├── workers/        # 知识重建、用量汇总
├── config.py
├── db.py
├── models.py
└── main.py
migrations/         # Alembic
scripts/            # seed_knowledge.py / reindex_knowledge.py
```

## 本地启动

```bash
python -m venv .venv
.venv/Scripts/activate            # Linux: source .venv/bin/activate
pip install -e ".[dev,embedding]"
cp .env.example .env              # 填写 DASHSCOPE_API_KEY
alembic upgrade head
python scripts/seed_knowledge.py
python scripts/reindex_knowledge.py
python scripts/dev.py --reload
```

仅做接口联调时可只装 `.[dev]`，跳过 embedding 与 reindex。

> Windows 本地开发请用 `scripts/dev.py` 启动（SelectorEventLoop）；Linux 用
> `uvicorn edu_ai.main:app --port 8002`。

### 本机联调（复用 kb_edu 的 embedding 依赖）

当前 `customer_service_edu/.venv` 没有 `torch` / `sentence-transformers`，而
`C:\data\python_data\kb_edu\.venv` 已具备 bge-m3 的运行依赖。可这样启动与重建索引：

```powershell
cd PRD\customer_ai_edu
$env:PYTHONPATH="src;C:\data\python_data\yxp_edu_file\PRD\customer_service_edu\.venv\Lib\site-packages"
# 启动服务
C:\data\python_data\kb_edu\.venv\Scripts\python.exe scripts\dev.py --port 8002
# 重建向量（10 个切片）
C:\data\python_data\kb_edu\.venv\Scripts\python.exe scripts\reindex_knowledge.py
```

> `PYTHONPATH` 中客服 venv 放在前面，确保使用 `pymilvus 2.6.17`（与 Milvus 2.5.5 的 ORM API 匹配），
> 而不是 `kb_edu` 中的 3.0.1。客服库地址由 `.env` 的 `CUSTOMER_SERVICE_URL` 指定，本机为
> `http://127.0.0.1:8010`。

首次调用 `reindex_knowledge.py` 或执行检索前，需要先创建 Milvus collection；
`knowledge/milvus_store.py` 的 `get_collection()` 会自动建表、建索引（已验证可连通
`http://192.168.168.100:19530`，collection 名 `edu_cs_knowledge_v1`）。

## 接口

- `GET /health` 存活
- `GET /ready` 就绪（PostgreSQL + Milvus）
- 内部接口统一由客服服务携带 `X-Internal-Service-Token` 调用：
  - `POST /internal/v1/agent/runs` 创建并同步执行一次 AgentRun（按 `request_id` 幂等）
  - `POST /internal/v1/agent/runs/{run_id}/confirm` 客服确认后执行已准备的动作
  - `POST /internal/v1/agent/runs/{run_id}/cancel` 取消运行（返回 204）
  - `GET /internal/v1/agent/runs/{run_id}` 查询运行结果

## 约定

- 会话与消息的正本在客服库，本服务不写业务库。
- 所有查询必须带 `tenant_id`；总部可跨租户，经销商只能看自己与总部共享内容。
- 模型只输出结构化决策；写操作由客服服务二次确认后落库。
- 密钥只放环境变量，不写进代码与日志。
