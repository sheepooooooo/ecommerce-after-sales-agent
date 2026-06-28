# 真实多轮确认与会话状态设计

本文档说明售后 Agent 当前阶段新增的多轮确认机制。该机制只用于本地模拟工单创建前的安全确认，不是长期记忆，也不是生产级会话系统。

## 为什么单条请求确认不等于真实多轮确认

此前系统支持在同一条请求中传入 `confirm_ticket_creation=true`。这种方式适合测试和 API 自动化验收，但不等于真实对话：

- 用户第一轮说“帮我给 ORD10003 创建售后工单”时，系统需要先说明会写入本地模拟数据库，并等待用户确认。
- 用户第二轮只说“确认”时，系统必须记得上一轮的待办动作和订单号。
- 如果不同用户或不同会话同时存在，确认动作不能串到别的会话。

因此本阶段新增 `session_id` 和 SQLite 持久化会话状态，让第二轮请求可以恢复上一轮 pending action。

## 核心字段

会话状态存储在 SQLite 表 `conversation_sessions` 中：

```text
session_id TEXT PRIMARY KEY
pending_action TEXT
pending_order_id TEXT
pending_payload TEXT
conversation_status TEXT
created_at TEXT
updated_at TEXT
```

字段含义：

- `session_id`：一次多轮会话的稳定标识。API 请求可传入；未传时服务端生成并在响应中返回。
- `pending_action`：当前待确认动作，例如 `create_ticket`。
- `pending_order_id`：待确认动作关联的订单号，例如 `ORD10003`。
- `pending_payload`：保存上一轮必要上下文，例如原始用户问题、订单号、request_id。
- `conversation_status`：会话状态，例如 `idle`、`pending_confirmation`、`completed`、`cancelled`。
- `created_at` / `updated_at`：本地模拟数据库中的创建与更新时间。

## 状态流转

```text
idle
  -> 用户请求创建工单且包含订单号
  -> pending_confirmation

pending_confirmation
  -> 同一 session 输入“确认”
  -> 创建一张本地模拟工单
  -> completed，并清除 pending_action

pending_confirmation
  -> 同一 session 输入“取消”
  -> cancelled，并清除 pending_action

idle / completed / cancelled
  -> 输入“确认”
  -> 返回“当前没有待确认操作”，不写数据库
```

缺订单号创建工单时，系统先返回 `missing_order_id`，不保存 pending action，也不进入确认。

## 多轮请求示例

第一轮：

```json
{
  "user_query": "帮我给 ORD10003 创建售后工单"
}
```

响应要点：

```json
{
  "session_id": "由服务端生成",
  "intent": "create_ticket",
  "answer_status": "ticket_confirmation_required",
  "confirmation_required": true,
  "tool_used": null
}
```

第二轮：

```json
{
  "session_id": "第一轮返回的 session_id",
  "user_query": "确认"
}
```

响应要点：

```json
{
  "session_id": "同一个 session_id",
  "intent": "create_ticket",
  "answer_status": "answered",
  "tool_used": "order_tool.create_ticket",
  "data": {
    "ticket": {
      "order_id": "ORD10003"
    }
  }
}
```

取消示例：

```json
{
  "session_id": "第一轮返回的 session_id",
  "user_query": "取消"
}
```

系统会清除 pending action，不写入工单。

## 会话隔离策略

`session_id` 是会话状态的主键。确认或取消时只读取同一个 `session_id` 下的 pending action。

例如：

- A 会话保存了 `ORD10003` 的 `create_ticket` pending action；
- B 会话输入“确认”；
- 系统只检查 B 会话，发现没有 pending action，因此不会创建 A 会话的工单。

当前实现使用 SQLite 持久化，不使用进程内字典，因此服务函数多次调用之间仍能恢复状态。

## 当前局限

- 这不是长期记忆，只保存本地模拟确认流程所需的短期 pending action。
- 这不包含用户身份认证，`session_id` 不能替代真实登录态或权限系统。
- 这不是生产级会话系统，没有 Redis、分布式锁、过期清理、审计后台或高可用设计。
- 当前只对模拟工单创建做多轮确认，不让 LLM 自主决定写库。
- 当前仍不执行真实退款、真实取消订单、真实物流变更或真实客服转接。
