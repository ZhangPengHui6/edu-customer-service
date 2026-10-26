# 学习机智能客服 — 已确认架构基线

| 项 | 内容 |
|---|---|
| 版本 | v1.0 |
| 日期 | 2026-10-26 |
| 状态 | **已确认，Phase 0 骨架依据** |
| 关联 | [客服 PRD](customer_service_edu_PRD.md) · [AI PRD](customer_ai_edu_PRD.md) · [环境配置](../config.md) |

---

## 1. 范围与原则

### 1.1 MVP 范围

**售后**：订单物流、硬件故障、保修维修、政策咨询、投诉转人工。

**不做（Phase 2+）**：售前导购、设备激活绑定、课程/会员、学习功能、语音/视频、工作台前端。

### 1.2 架构原则

1. **两服务、两数据库**：`customer-service-edu` 管会话/工单/维修；`customer-ai-edu` 管 Agent Run/工具/知识。
2. **业务数据不直连**：AI 通过 ACL 适配器调用业务系统；Phase 0 用 PostgreSQL 测试表 + Mock。
3. **租户先行**：所有业务表带 `tenant_id`，所有查询强制过滤；JWT 必带租户。
4. **两阶段写**：AI 只准备决策；`confirm` 后才产生副作用。
5. **知识双库**：PostgreSQL 存文章/版本/权限；Milvus 存向量 + BM25。
6. **可回滚**：Alembic 管表结构；seed 幂等；Compose 一键起停。

---

## 2. 目录结构

```text
yxp_edu_file/
├─ config.md                         # 环境与密钥（不提交 Git）
├─ PRD/
│  ├─ customer_service_edu_PRD.md
│  ├─ customer_ai_edu_PRD.md
│  ├─ 00_ARCHITECTURE_CONFIRMED.md   # 本文件
│  ├─ customer_service_edu/          # 客服服务
│  │  ├─ pyproject.toml
│  │  ├─ README.md
│  │  ├─ .env.example
│  │  ├─ Dockerfile
│  │  ├─ alembic.ini
│  │  ├─ migrations/
│  │  │  ├─ env.py
│  │  │  ├─ script.py.mako
│  │  │  └─ versions/0001_init.py
│  │  ├─ scripts/
│  │  │  └─ seed.py
│  │  ├─ src/edu_cs/
│  │  │  ├─ main.py
│  │  │  ├─ config.py
│  │  │  ├─ db.py
│  │  │  ├─ models.py
│  │  │  ├─ api/
│  │  │  │  ├─ health.py
│  │  │  │  ├─ conversations.py   # Phase 1
│  │  │  │  ├─ messages.py
│  │  │  │  ├─ handoffs.py
│  │  │  │  ├─ repairs.py
│  │  │  │  └─ admin.py
│  │  │  ├─ schemas/
│  │  │  ├─ repositories/
│  │  │  ├─ services/
│  │  │  └─ workers/
│  │  └─ tests/
│  └─ customer_ai_edu/               # AI 服务
│     ├─ pyproject.toml
│     ├─ README.md
│     ├─ .env.example
│     ├─ Dockerfile
│     ├─ alembic.ini
│     ├─ migrations/
│     │  ├─ env.py
│     │  ├─ script.py.mako
│     │  └─ versions/0001_init.py
│     ├─ scripts/
│     │  ├─ seed_knowledge.py
│     │  └─ reindex_knowledge.py
│     ├─ src/edu_ai/
│     │  ├─ main.py
│     │  ├─ config.py
│     │  ├─ db.py
│     │  ├─ models.py
│     │  ├─ api/
│     │  │  ├─ health.py
│     │  │  ├─ runs.py             # Phase 1
│     │  │  └─ knowledge.py
│     │  ├─ agent/
│     │  │  ├─ factory.py
│     │  │  ├─ prompt.py
│     │  │  ├─ output.py
│     │  │  ├─ skills/
│     │  │  ├─ tools/
│     │  │  └─ validators/
│     │  ├─ knowledge/
│     │  │  ├─ embedder.py
│     │  │  ├─ milvus_store.py
│     │  │  └─ service.py
│     │  ├─ schemas/
│     │  ├─ repositories/
│     │  ├─ services/
│     │  └─ workers/
│     └─ tests/
└─ deploy/
   ├─ docker-compose.yml
   ├─ .env.example
   └─ init/
      └─ 00_create_databases.sql
```

> 只列 Phase 0/1 会落地的文件；空目录由 `__init__.py` 占位，后续按模块补齐。

---

## 3. 数据库命名与规范

### 3.1 数据库

| 库 | 归属 | 说明 |
|---|---|---|
| `edu_customer_service` | 客服服务 | 会话、消息、工单、维修、设备、租户、坐席、审计 |
| `edu_ai_service` | AI 服务 | Agent Run、工具调用、知识元数据、动作、评测 |

### 3.2 命名规范

| 项 | 规范 |
|---|---|
| 表名 | 小写复数 snake_case，如 `conversations`、`repair_tickets` |
| 字段 | snake_case；外键 `<table_singular>_id` |
| 主键 | 业务表 `id uuid`（`gen_random_uuid()`）；流水表 `id bigint generated always as identity` |
| 外部 ID | `message_id` / `request_id` / `run_id` 等业务可读 ID，单独唯一索引 |
| 时间 | `timestamptz`；`created_at`、`updated_at`、`deleted_at`（仅软删表） |
| 金额 | `numeric(12,2)` |
| 枚举 | `varchar(32)` + `CHECK`（不用 PG native enum，便于演进） |
| JSON | `jsonb`；高频过滤字段单独建列 |
| 索引 | 外键、租户、状态、时间；部分唯一索引用 `WHERE` |
| 大小写 | 全部小写；禁止引号混合大小写 |

### 3.3 租户模型

```text
tenants
  id uuid pk
  code varchar(64) unique          -- hq / dlr_north / dlr_south
  type varchar(16)                 -- HQ | DEALER
  name varchar(128)
  parent_id uuid null -> tenants.id -- 经销商指向 HQ
  status varchar(16)               -- active | disabled
```

规则：

- 总部 `parent_id is null`；经销商 `parent_id = HQ.id`。
- 所有业务表 `tenant_id not null`；AI 库不建跨库外键，只存值。
- 应用层统一注入租户过滤；后续可加 PostgreSQL RLS。
- 总部坐席可跨租户；经销商坐席只能本租户；跨租户需 `audit_logs` 记录。
- 公共知识归属 HQ，`knowledge_articles.scope = all_dealers|tenant`：`all_dealers` 由 HQ 维护，所有经销商可检索；`tenant` 仅归属租户可见。

### 3.4 客服库表清单

| # | 表 | 类型 | 说明 |
|---|---|---|---|
| 1 | `tenants` | 主数据 | 总部/经销商 |
| 2 | `users` | 主数据 | 家长/学生/坐席账号；`(tenant_id, external_id)` 唯一 |
| 3 | `agents` | 主数据 | 坐席档案、并发上限 |
| 4 | `skill_groups` | 主数据 | 技能组、SLA、路由策略 |
| 5 | `agent_skills` | 关联 | 坐席-技能组 |
| 6 | `conversations` | 业务 | 会话；`(tenant_id,user_id,channel)` 单开放部分唯一 |
| 7 | `conversation_turns` | 业务 | 轮次；COLLECTING/RUNNING 各一条部分唯一 |
| 8 | `messages` | 业务 | 消息；`message_id` 唯一；`(conversation_id,input_revision)` 唯一 |
| 9 | `attachments` | 业务 | 图片/附件元数据，文件在 MinIO |
| 10 | `handoffs` | 业务 | 转人工工单 |
| 11 | `handoff_events` | 流水 | 工单状态流水 |
| 12 | `devices` | 主数据 | 设备 SN、型号、归属、激活 |
| 13 | `warranties` | 主数据 | 保修起止、类型、状态 |
| 14 | `device_bindings` | 主数据 | 家长/学生绑定关系 |
| 15 | `repair_tickets` | 业务 | 维修单（寄修/到店）；`repair_no` 唯一 |
| 16 | `repair_events` | 流水 | 维修状态流水 |
| 17 | `service_centers` | 主数据 | 服务网点，按租户维护 |
| 18 | `orders` | Phase 0 镜像 | 测试用订单；后续由 OMS ACL / Mock 替代 |
| 19 | `order_items` | Phase 0 镜像 | 订单明细 |
| 20 | `logistics_events` | Phase 0 镜像 | 物流节点 |
| 21 | `realtime_outbox` | 基础设施 | 事务性 Outbox；`sequence` 单调 |
| 22 | `outbox_dead_letters` | 基础设施 | 死信 |
| 23 | `csat_surveys` | 业务 | 满意度 |
| 24 | `canned_replies` | 运营 | 快捷话术 |
| 25 | `audit_logs` | 审计 | 操作审计（含跨租户访问） |

> `orders` / `order_items` / `logistics_events` 只用于 Phase 0 联调与测试数据；接入真实 OMS 后改为只读 ACL 查询，不把外部订单表直接暴露给 AI。

### 3.5 AI 库表清单

| # | 表 | 类型 | 说明 |
|---|---|---|---|
| 1 | `agent_runs` | 业务 | Run 状态机、`run_id`/`request_id` 幂等、心跳、token/成本 |
| 2 | `agent_tool_calls` | 业务 | 工具调用审计 |
| 3 | `knowledge_articles` | 知识 | 文章主表、版本、状态、生效期、适用范围 |
| 4 | `knowledge_chunks` | 知识 | 切片元数据；`id` 即 Milvus `chunk_id` |
| 5 | `knowledge_feedback` | 知识 | 坐席/用户反馈 |
| 6 | `action_requests` | 业务 | 待确认/已执行动作，幂等 |
| 7 | `prompt_versions` | 运营 | 提示词版本与灰度 |
| 8 | `agent_evaluations` | 评测 | 离线/在线评测结果 |
| 9 | `bad_cases` | 评测 | bad case 库 |
| 10 | `model_usage_daily` | 成本 | 按日/租户/模型聚合 |

### 3.6 关键约束

```sql
-- 会话：同一租户/用户/渠道最多一个开放会话
CREATE UNIQUE INDEX uq_conversations_open
  ON conversations (tenant_id, user_id, channel)
  WHERE mode IN ('AI','QUEUED','HUMAN','REPAIR');

-- 轮次：同一会话最多一个 COLLECTING、一个 RUNNING
CREATE UNIQUE INDEX uq_turns_collecting
  ON conversation_turns (conversation_id) WHERE status = 'COLLECTING';
CREATE UNIQUE INDEX uq_turns_running
  ON conversation_turns (conversation_id) WHERE status = 'RUNNING';

-- 消息幂等（AI 消息的 input_revision 为空，不参与该索引）
CREATE UNIQUE INDEX uq_messages_message_id ON messages (message_id);
CREATE UNIQUE INDEX uq_messages_revision
  ON messages (conversation_id, input_revision) WHERE input_revision IS NOT NULL;

-- 工单：同一会话/用户最多一个开放工单
CREATE UNIQUE INDEX uq_handoffs_open_conversation
  ON handoffs (tenant_id, conversation_id) WHERE status IN ('waiting','active');
CREATE UNIQUE INDEX uq_handoffs_open_user
  ON handoffs (tenant_id, user_id) WHERE status IN ('waiting','active');

-- AI Run 幂等
CREATE UNIQUE INDEX uq_agent_runs_run_id ON agent_runs (run_id);
CREATE UNIQUE INDEX uq_agent_runs_request_id ON agent_runs (request_id);
```

---

## 4. Milvus 设计

### 4.1 Collection

| 项 | 值 |
|---|---|
| Collection | `edu_cs_knowledge_v1` |
| 向量 | `vector` FLOAT_VECTOR，**1024 维**（bge-m3） |
| 索引 | `AUTOINDEX`，`COSINE` |
| 标量索引 | `tenant_id`、`product_model`、`doc_type`（INVERTED） |
| 主键 | `chunk_id` VARCHAR(64)，等于 PG `knowledge_chunks.id` |
| 分区键（可选） | `tenant_id`（租户数 > 20 时启用） |

### 4.2 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `chunk_id` | VARCHAR(64) PK | 与 PG 一致 |
| `vector` | FLOAT_VECTOR(1024) | bge-m3 dense |
| `text` | VARCHAR(16384) | 切片原文 |
| `tenant_id` | VARCHAR(64) | 归属租户（HQ 公共知识为 HQ） |
| `article_id` | VARCHAR(64) | 文章 ID |
| `product_model` | VARCHAR(64) | 适用型号；空=通用 |
| `doc_type` | VARCHAR(32) | manual/faq/policy/troubleshooting/script/course/firmware/store |
| `version` | INT64 | 文章版本号 |
| `status` | VARCHAR(16) | published/archived |
| `effective_from` | INT64 | epoch 秒；0=立即生效 |
| `effective_to` | INT64 | epoch 秒；0=长期 |
| `chunk_index` | INT64 | 切片序号 |
| `source_title` | VARCHAR(512) | 来源标题 |

### 4.3 BM25

Milvus 2.5.5 支持 BM25 Function。Phase 1 第一周先落地 dense 检索；第二周增加：

- 新增 `sparse` 稀疏向量字段 + `text` 的 BM25 Function；
- 查询用 `hybrid_search`，dense + sparse 加权融合（RRF）；
- 中文 analyzer 使用 `chinese`。

> 在 BM25 落地前，关键词兜底用 PostgreSQL `ILIKE`/`tsvector`，保证功能可用。

### 4.4 写入流程

```text
文章发布
  → PG knowledge_articles / knowledge_chunks（事务）
  → 生成 embedding（bge-m3）
  → Milvus upsert（chunk_id 幂等）
  → 更新 chunks.indexed_at
  → 失败：PG 标记 indexing=failed，重试任务补偿
```

删除/下线：先更新 PG 状态，再按 `article_id` 删除 Milvus 向量（软删优先）。

---

## 5. 接口契约清单

### 5.1 外部 API（C 端 / 坐席端）

统一前缀 `/api/v1`；认证 `Authorization: Bearer <JWT>`；JWT 必含 `user_id`、`role`、`tenant_id`、`channel`、`exp`。

#### 认证（开发期）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/demo-token` | 开发用；入参 `{user_id, role, tenant_id}`；生产替换为 SSO |

#### 会话与消息

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/conversations/current` | 获取/创建当前开放会话；返回 `{conversation_id, mode, is_processing}` |
| GET | `/conversations/{id}` | 会话详情 + 最近消息 |
| POST | `/conversations/{id}/close` | 用户主动结束 |
| POST | `/chat/messages` | 发送消息；`message_id` 幂等；支持 text/image |
| GET | `/chat/history?after_sequence=` | 增量历史（游标） |
| GET | `/conversations/{id}/messages?after_sequence=` | 会话内消息分页 |

`POST /chat/messages` 请求：

```json
{
  "message_id": "msg_client_uuid",
  "conversation_id": "conv_uuid",
  "type": "text",
  "content": {"text": "开不了机"},
  "client_time": "2026-10-26T10:00:00+08:00"
}
```

图片消息：`type=image`，`content={"attachment_id": "att_uuid"}`。

#### 附件

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/attachments/presign` | 获取 MinIO 预签名上传 URL |
| POST | `/attachments/complete` | 上报 sha256/size，触发病毒扫描 |
| GET | `/attachments/{id}` | 获取短时下载 URL |

#### 转人工（坐席）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/handoffs?status=&skill_group=&priority=` | 排队列表 |
| POST | `/handoffs/{id}/accept` | 接单 |
| POST | `/handoffs/{id}/messages` | 坐席回复 |
| POST | `/handoffs/{id}/transfer` | 转接 |
| POST | `/handoffs/{id}/resolve` | 结单；`close_reason` 必填 |
| GET | `/handoffs/{id}/events` | 流水 |

#### 维修

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/repairs` | 创建维修单（寄修/到店） |
| GET | `/repairs?status=&device_sn=` | 列表 |
| GET | `/repairs/{id}` | 详情 + 流水 |
| POST | `/repairs/{id}/cancel` | 取消（未受理） |
| GET | `/repairs/{id}/events` | 状态流水 |

#### 设备/保修

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/devices/{sn}` | 设备详情（归属校验） |
| GET | `/devices/{sn}/warranty` | 保修状态与依据 |
| GET | `/devices/{sn}/repairs` | 历史维修 |

#### 管理（总部/经销商）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/admin/metrics` | 核心指标（按租户过滤） |
| GET/POST | `/admin/tenants` | 租户管理（仅 HQ） |
| GET/POST | `/admin/agents` | 坐席 |
| GET/POST | `/admin/skill-groups` | 技能组 |
| GET | `/admin/audit-logs` | 审计 |
| GET/POST | `/admin/canned-replies` | 话术 |

#### WebSocket

| 路径 | 说明 |
|---|---|
| `GET /api/v1/realtime?ticket=<short_jwt>` | 首帧外传 ticket；支持 `after_sequence` 补发；心跳 30s |

事件：`message.created`、`conversation.updated`、`handoff.changed`、`repair.changed`、`ping`。

### 5.2 内部 API（客服 ↔ AI）

统一前缀 `/internal/v1`；双头认证：`Authorization: Bearer <user_jwt>` + `X-Internal-Service-Token`。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/agent/runs` | 启动 Run；`request_id` 幂等；返回事件 |
| POST | `/agent/runs/{id}/confirm` | 确认；校验归属/状态/`input_revision`/过期 |
| POST | `/agent/runs/{id}/cancel` | 取消 |
| GET | `/agent/runs/{id}` | 查询 Run 与工具调用 |
| POST | `/agent/runs/{id}/feedback` | 人工反馈（好/坏/修正） |
| POST | `/knowledge/search` | 内部检索（评测/坐席助手） |
| POST | `/knowledge/reindex` | 重建索引（管理员） |

`POST /agent/runs` 请求（关键字段）：

```json
{
  "request_id": "turn_uuid:1",
  "tenant_id": "tenant_uuid",
  "channel": "app",
  "conversation_id": "conv_uuid",
  "turn_id": "turn_uuid",
  "user_id": "user_uuid",
  "input_revision": 3,
  "messages": [{"message_id": "msg_uuid", "type": "text", "content": {"text": "开不了机"}}],
  "history": [],
  "context": {"device_sn": "SN...", "order_id": "ORDER_..."},
  "options": {"max_tool_calls": 8, "stream": false}
}
```

事件类型：

| `event_type` | 含义 | 后续动作 |
|---|---|---|
| `run_completed` | 只读回答完成 | 客服落消息 |
| `run_decision_prepared` | 待确认（页面动作/写操作） | 客服校验 revision 后 confirm/cancel |
| `run_handoff_requested` | 转人工 | 客服建工单 |
| `run_failed` | 失败 | 客服重试/兜底话术 |

### 5.3 外部业务系统（ACL）

| 系统 | 接口（示例） | Phase 0 |
|---|---|---|
| OMS | 订单列表/详情/物流/取消 | PG 测试表 + Mock |
| 设备/保修 | SN 查询/保修查询 | PG 测试表 + Mock |
| 维修 | 建单/进度/取消 | 本服务 `repair_tickets` + Mock |
| 知识 | 无 | 本服务 PG + Milvus |

> 真实系统接入时只替换 `services/acl/*` 实现，不改工具与 API 契约。

### 5.4 错误码

| HTTP | code | 说明 |
|---|---|---|
| 400 | `INVALID_MESSAGE` | 消息格式/类型不支持 |
| 401 | `UNAUTHORIZED` | Token 缺失/过期 |
| 403 | `TENANT_FORBIDDEN` | 跨租户越权 |
| 404 | `NOT_FOUND` | 资源不存在 |
| 409 | `DUPLICATE_MESSAGE` | 幂等命中（返回原结果） |
| 409 | `RUN_STATE_INVALID` | Run 状态不允许 |
| 409 | `INPUT_REVISION_STALE` | 输入已过期 |
| 422 | `VALIDATION_ERROR` | 参数校验失败 |
| 429 | `RATE_LIMITED` | 限流 |
| 503 | `AI_UNAVAILABLE` | AI 服务不可用 |

---

## 6. 测试数据计划

### 6.1 租户

| code | type | name | parent |
|---|---|---|---|
| `hq` | HQ | 学习机总部 | — |
| `dlr_north` | DEALER | 华北经销商 | `hq` |
| `dlr_south` | DEALER | 华南经销商 | `hq` |

### 6.2 用户

| external_id | 角色 | 租户 | 说明 |
|---|---|---|---|
| `parent_001` | customer | dlr_north | 家长，绑定 X5/X6 |
| `parent_002` | customer | dlr_north | 家长，设备已过保 |
| `parent_003` | customer | dlr_south | 家长，两台 S3 |
| `student_001` | customer | dlr_north | 学生子账号，监护人 `parent_001` |
| `agent_001` | agent | dlr_north | 经销商坐席，售后+投诉技能 |
| `agent_002` | agent | dlr_south | 经销商坐席，售后技能 |
| `admin_001` | admin | hq | 总部管理员 |

### 6.3 设备/保修

| SN | 型号 | 租户 | 归属 | 激活 | 保修 |
|---|---|---|---|---|---|
| `SNX5000001` | X5 | dlr_north | parent_001 | 2025-03-15 | 在保至 2027-03-14 |
| `SNX5000002` | X5 | dlr_north | parent_002 | 2025-05-20 | 已过保（2026-05-19） |
| `SNX6000001` | X6 | dlr_north | parent_001 | 2025-09-01 | 在保至 2027-08-31；学生账号绑定 |
| `SNS3000001` | S3 | dlr_south | parent_003 | 2026-01-10 | 在保至 2028-01-09 |
| `SNS3000002` | S3 | dlr_south | parent_003 | 2024-06-01 | 已过保（2026-05-31） |

### 6.4 订单

| 订单号 | 用户 | 状态 | 说明 |
|---|---|---|---|
| `ORDER_20251001` | parent_001 | delivered | X5 ¥3299，已签收 |
| `ORDER_20251002` | parent_002 | shipped | X5+保护壳 ¥3398，物流在途 |
| `ORDER_20251003` | parent_001 | paid | X6 ¥4999，未发货，可取消 |
| `ORDER_20251004` | parent_003 | delivered | S3 ¥1999 |
| `ORDER_20251005` | parent_003 | pending | 配件 ¥199，未支付 |

### 6.5 维修单

| ID | 设备 | 状态 | 方式 | 说明 |
|---|---|---|---|---|
| `REP_20251001` | SNX5000001 | completed | 到店 | 屏幕闪烁，保修内 |
| `REP_20251002` | SNX5000002 | diagnosing | 寄修 | 无法开机，已过保 |
| `REP_20251003` | SNX6000001 | created | 到店 | 触控失灵，保修内 |
| `REP_20251004` | SNS3000001 | repairing | 到店 | 电池异常，保修内 |
| `REP_20251005` | SNS3000002 | cancelled | 寄修 | 扬声器杂音，用户取消 |

### 6.6 知识文章（MVP 10 篇）

1. 学习机保修政策总览（`all_dealers`）
2. 报修与维修工单流程（`all_dealers`）
3. 屏幕闪烁排查指引
4. 设备无法开机排查指引
5. 电池续航异常排查指引
6. 触控失灵排查指引
7. 物流停滞处理口径（`all_dealers`）
8. 未发货订单取消规则（`all_dealers`）
9. 家长与学生学习数据隐私说明（`all_dealers`）
10. 投诉安抚与升级流程（`all_dealers`）

每篇带 `product_models`、`version=1`、`scope`、`tenant_id`（公共知识为 HQ）。

### 6.7 Seed 规则

- UUID 由 `uuid5(NAMESPACE_URL, "https://edu-cs.local/seed")` 派生，两个服务共用同一命名空间，重复执行 ID 不变。
- 检测到已有租户/文章即整体跳过，全部数据在同一事务内提交，不会出现半套数据。
- 不生成真实手机号/地址；用 `138****0001`、`北京市朝阳区****`。
- `scripts/seed.py` 只写客服库；`scripts/seed_knowledge.py` 只写 AI 库文章与切片，向量由 `scripts/reindex_knowledge.py` 单独生成。

---

## 7. 端口与网络

| 服务 | 端口 | 暴露 |
|---|---|---|
| customer-service-edu | 8000 | 内网/反代 |
| customer-ai-edu | 8002 | 仅内网 |
| PostgreSQL | 5432 | 内网 |
| Redis | 6379 | 内网 |
| Milvus | 19530 | 内网 |
| MinIO | 9000/9001 | 内网 |
| ecommerce-service（现有） | 8001 | 不占用 |

---

## 8. Phase 0 交付物

1. 两个服务可启动，`/health`、`/ready` 正常。
2. `edu_customer_service`、`edu_ai_service` 建库成功，Alembic 基线迁移可执行。
3. Seed 脚本生成 §6 的测试数据。
4. `deploy/docker-compose.yml` 一键起停。
5. README 写明启动、迁移、seed、测试命令。
6. 修复参考代码 C-01–C-15（在骨架中直接按修复后的写法实现）。

### 8.1 完成情况（2026-10-26）

| 项 | 状态 |
|---|---|
| 两个库 + 迁移 | ✅ 已执行（客服 25 表、AI 10 表） |
| 客服 seed | ✅ 3 租户 / 7 用户 / 5 设备 / 5 订单 / 5 维修单 / 2 会话 |
| 知识 seed | ✅ 10 篇文章 / 10 个切片 |
| Milvus collection | ✅ `edu_cs_knowledge_v1` 已建（dense + 标量索引） |
| `/ready` | ✅ 客服 DB+Redis；AI DB+Milvus |
| 单测 | ✅ 两个服务各 2 个用例 |
| 知识向量 | ⏳ 待安装 `sentence-transformers` + bge-m3 权重后执行 `reindex_knowledge.py` |
| Compose 实机起停 | ⏳ 待在有 Docker 的 192.168.168.100 上执行 |

---

## 9. 变更记录

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.0 | 2026-10-26 | 确认多租户、售后 MVP、PG+Milvus、单机 Compose；确定目录/表/接口契约 |
