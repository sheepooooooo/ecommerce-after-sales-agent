# 多轮信息补全与任务续办

本文档说明当前售后 Agent 在缺少订单号时，如何保存短期任务状态，并在用户下一轮补充订单号后续办原任务。该能力只覆盖有限售后任务，不是长期用户记忆，也不是通用 Planner。

## 为什么追问不等于续办

只返回“请提供订单号”只能完成信息追问。如果用户下一轮只说 `ORD10003`，系统还需要知道上一轮到底是在退款判断、订单查询、创建工单，还是受控复合任务中等待订单号。

因此本项目在缺订单号时会持久化短期 pending 任务。下一轮同一 `session_id` 输入订单号时，系统优先读取 pending 状态，恢复原任务，而不是把订单号误判成新的普通订单查询。

## 状态字段

- `session_id`：一次短期任务会话的标识。调用方可传入；未传时服务端生成。
- `pending_action`：等待补充信息或确认的动作，例如 `refund_eligibility`、`order_lookup`、`create_ticket`、`refund_then_ticket_if_ineligible`。
- `pending_order_id`：已知但尚未确认写库时的订单号；缺订单号阶段为 `NULL`。
- `pending_reason`：等待原因，例如 `missing_order_id` 或 `awaiting_confirmation`。
- `workflow_type`：复合任务类型；当前仅支持 `refund_then_ticket_if_ineligible`。
- `pending_payload`：保存必要安全上下文，例如原始 intent、是否为复合任务、是否要求不可退款后建工单、幂等 key。
- `conversation_status`：`awaiting_order_id`、`pending_confirmation`、`completed`、`cancelled`、`interrupted` 等短期状态。

## 四组对话示例

### 退款资格续办

```text
用户：帮我退款
系统：请提供订单号。
用户：ORD10003
系统：恢复退款资格判断，调用退款规则 Tool，返回该订单是否可退款。
```

### 订单查询续办

```text
用户：帮我查询订单状态
系统：请提供订单号。
用户：ORD10003
系统：恢复订单查询，调用订单 Tool，返回支付、物流和退款状态。
```

### 创建工单续办

```text
用户：帮我创建售后工单
系统：请提供订单号。
用户：ORD10003
系统：进入工单确认，不写数据库。
用户：确认
系统：复用已有确认和幂等机制，创建本地模拟工单。
```

### 受控复合任务续办

```text
用户：订单能退吗，不行就建工单
系统：请提供订单号。
用户：ORD10003
系统：恢复 refund_then_ticket_if_ineligible，先判断退款资格；不可直接退款时进入工单确认。
用户：确认
系统：创建本地模拟工单；重复确认返回同一工单。
```

## 状态变化

```text
idle
  -> awaiting_order_id
  -> completed
```

适用于退款资格和订单查询续办。

```text
idle
  -> awaiting_order_id
  -> pending_confirmation
  -> completed
```

适用于创建工单和不可退款后建工单的复合任务。

```text
awaiting_order_id
  -> cancelled
```

用户说“取消”“那算了”“我不想办了”时清理 pending，不调用工具。

```text
awaiting_order_id
  -> interrupted
  -> 新请求正常路由
```

用户没有补订单号，而是提出新的明确业务问题时，中断旧 pending，并记录 `pending_task_interrupted` trace。

## Trace 事件

续办相关事件会进入持久化 trace，并经过订单号脱敏：

- `pending_task_created`
- `pending_task_resumed`
- `pending_task_cancelled`
- `pending_task_interrupted`

正常响应不会展示完整内部 trace；可通过 `GET /agent/traces/{request_id}` 查询脱敏后的事件。

## 与长期记忆的区别

该机制只保存完成当前售后任务所需的短期状态，不保存长期用户画像，不跨用户身份做记忆合并，也不让 LLM 基于历史状态自主决定退款或写库。

## 当前局限

- 仅支持有限业务任务：退款资格、订单查询、创建工单缺订单号补全，以及 `refund_then_ticket_if_ineligible`。
- 使用单机 SQLite，不是分布式会话系统。
- 没有真实用户身份认证和权限隔离。
- 不是通用对话记忆系统。
- 非生产级高可用 session 服务。
