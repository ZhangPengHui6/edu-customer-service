# 学伴客服前端

学习机售后智能客服的 Web 前端，包含两个使用端：

- **家长端 `/app`**：订单、物流、设备保修、维修进度、AI 客服与转人工。移动端优先，桌面浏览器下以手机壳形式居中显示。
- **坐席工作台 `/staff`**：待接入/进行中队列、客户上下文、人工回复、结束会话。桌面三栏布局。

界面按 `customer_service_prototype.pen` 原型实现，接口只使用 `customer_service_edu` 已提供的 API，没有前端本地 Mock 业务数据（登录使用后端演示 Token 接口）。

## 技术栈

| 项 | 选择 |
|---|---|
| 框架 | React 18 + TypeScript |
| 构建 | Vite 6 |
| 路由 | react-router-dom 6 |
| 图标 | lucide-react |
| 样式 | 原生 CSS + 设计变量（`src/styles.css`），未引入 UI 组件库 |
| 实时更新 | 轮询（客服消息 2.5s、坐席消息 3s、坐席队列 5s） |

## 本地运行

前置条件：Node.js 18+（建议 20+），并已启动以下后端服务：

- 客服 API：`http://127.0.0.1:8010`
- AI 服务：`http://127.0.0.1:8002`
- PostgreSQL / Redis / Milvus 可访问

```bash
cd yxp_edu_file/PRD/customer_service_frontend
npm install
cp .env.example .env
npm run dev
```

打开 `http://127.0.0.1:5174`。

> 5174 是刻意选择的端口：本机 5173 已被另一个项目占用。`vite.config.ts` 设置了 `strictPort`，端口冲突时会直接失败而不是静默换端口。

### 环境变量

```ini
VITE_API_BASE_URL=http://127.0.0.1:8010
```

修改后需要重启 Vite。

### 后端 CORS

客服服务 `customer_service_edu/.env` 中的 `CORS_ORIGINS` 必须包含前端来源，例如：

```ini
CORS_ORIGINS=http://localhost:5174,http://127.0.0.1:5174,http://192.168.168.100:5174
```

局域网访问时，把实际访问地址加入该列表并重启客服 API。

## 演示账号

登录页直接点击账号卡片即可获取演示 Token（后端需开启 `DEMO_AUTH_ENABLED=true`）。

| 姓名 | 角色 | external_id | 租户 |
|---|---|---|---|
| 张伟 | 家长 | `parent_001` | `dlr_north` |
| 李娜 | 家长 | `parent_002` | `dlr_north` |
| 王强 | 家长 | `parent_003` | `dlr_south` |
| 陈晓 | 坐席 | `agent_001` | `dlr_north` |
| 刘悦 | 坐席 | `agent_002` | `dlr_south` |

Token 保存在 `localStorage` 的 `edu-cs-auth` 下。

## 页面与接口

### 家长端

| 路由 | 页面 | 主要接口 |
|---|---|---|
| `/app` | 首页：服务入口、设备、最近订单、售后 | `GET /conversations/current`、`/orders`、`/devices`、`/repairs` |
| `/app/orders` | 订单列表与状态筛选 | `GET /api/v1/orders` |
| `/app/orders/:orderNo` | 订单详情、进度、物流、收货信息 | `GET /api/v1/orders/{order_no}` |
| `/app/devices` | 设备与保修状态 | `GET /api/v1/devices` |
| `/app/repairs` | 维修工单列表 | `GET /api/v1/repairs` |
| `/app/repairs/:repairNo` | 维修详情与事件时间线 | `GET /api/v1/repairs/{repair_no}` |
| `/app/chat` | AI 客服 / 排队 / 人工会话 | `GET /conversations/current`、`GET /conversations/{id}`、`POST /conversations/{id}/messages` |
| `/app/profile` | 账号、服务入口、退出登录 | 无（本地会话） |

家长端不使用 WebSocket：聊天页每 2.5 秒拉取一次会话详情，用 `is_processing` 显示「AI 正在思考」。AI 超过 45 秒仍未结束时，页面会提示可转人工。

### 坐席工作台

| 路由 | 页面 | 主要接口 |
|---|---|---|
| `/staff`、`/staff/:handoffId` | 队列 + 会话 + 客户上下文 | `GET /api/v1/staff/handoffs` |
| 接入 | 接入待处理会话 | `POST /api/v1/staff/handoffs/{id}/accept` |
| 会话消息 | 拉取 / 发送人工回复 | `GET /api/v1/conversations/{id}/messages`、`POST /api/v1/staff/handoffs/{id}/messages` |
| 客户信息 | 订单 / 设备 / 维修概览 | `GET /api/v1/staff/handoffs/{id}/context` |
| 结束 | 填写小结并结束会话 | `POST /api/v1/staff/handoffs/{id}/resolve` |

队列每 5 秒刷新；消息每 3 秒刷新。结束会话后保留当前会话快照用于展示，队列中自动移除。

## 与原型/后端的取舍

- **没有家长主动取消订单的按钮**：后端未开放家长侧取消接口，取消只能由 AI 在对话中完成。订单详情只提供「联系客服」。
- **没有单独的「转人工」接口**：家长点右上角「人工」时发送一条「请帮我转人工客服」消息，由 AI 判定并创建转人工工单。
- **权限做了简化**：目前仅区分 `customer` 与坐席/管理员，页面级路由有基本拦截；接口侧权限仍由后端 JWT 控制。正式环境需要补前端细粒度权限。
- **没有实现原型之外的功能**：坐席转接、服务小结列表、快捷回复管理、帮助中心、经营看板等均未接入，因为后端暂无对应接口。
- **订单状态筛选**包含全部六种状态；维修筛选为全部/进行中/已结束。

## 脚本

```bash
npm run dev        # 开发服务，0.0.0.0:5174
npm run typecheck  # tsc --noEmit
npm run build      # 类型检查 + 生产构建到 dist/
npm run preview    # 预览生产构建，0.0.0.0:4173
```

## 目录

```text
src/
├── api/           # fetch 封装与 TypeScript 类型
├── auth/          # 演示 Token 登录、会话持久化
├── components/    # 布局与通用 UI
├── hooks/         # useAsync / usePolling
├── pages/
│   ├── customer/  # 家长端
│   └── staff/     # 坐席工作台
├── utils/         # 日期、金额、状态文案
├── App.tsx
├── main.tsx
└── styles.css     # 全站样式与设计变量
```
