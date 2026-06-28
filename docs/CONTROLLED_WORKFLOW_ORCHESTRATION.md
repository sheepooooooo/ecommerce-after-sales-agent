# 受控复合工作流编排设计

本文说明当前项目新增的 `refund_then_ticket_if_ineligible` 复合任务能力。它只用于一个固定售后场景：用户同时询问退款资格，并明确表示“如果不能退款就创建售后工单”。

## 为什么不是自由 Agent 编排

当前实现不是 Multi-Agent，也不是 LLM 自由选择工具。复合任务只允许走固定步骤：

1. 抽取订单号；
2. 查询模拟订单；
3. 调用退款资格 Tool；
4. 根据确定性结果决定是否进入工单确认。

LLM 不能决定是否退款，不能直接写工单，也不能绕过确认。

## 状态字段

- `workflow_type`：当前只支持 `refund_then_ticket_if_ineligible`。
- `task_plan`：固定计划，当前为 `extract_order_id -> lookup_order -> check_refund_eligibility -> decide_ticket_fallback`。
- `current_step`：当前执行到的步骤。
- `plan_status`：`completed`、`waiting_confirmation` 或 `stopped`。
- `fallback_requested`：用户是否明确要求兜底工单。
- `next_action`：下一步建议，例如 `refund_eligible_no_ticket`、`confirm_create_ticket`。
- `max_steps`：最大步骤数，当前为 6，用于防止未来扩展时出现无限循环。
- `executed_steps`：已执行步骤。

## 状态流转

```text
收到请求
  -> 缺订单号: missing_order_id，停止
  -> 高风险: human_handoff，停止
  -> 查询订单
       -> 订单不存在: manual_review，停止
       -> 订单存在: 检查退款资格
            -> eligible: answered，不创建工单
            -> not_eligible: ticket_confirmation_required，保存 pending_action
            -> manual_review: manual_review，停止
```

## 多轮确认

第一轮：

```json
{
  "user_query": "ORD10003 能退款吗？如果不能，帮我创建售后工单。"
}
```

若退款规则判断不可直接退款，系统返回 `ticket_confirmation_required`，同时把 `pending_action=create_ticket`、`pending_order_id=ORD10003` 和复合流程摘要保存到 SQLite 会话表。

第二轮：

```json
{
  "user_query": "确认",
  "session_id": "第一轮返回的 session_id"
}
```

服务层恢复上一轮 pending action，并复用现有工单创建与幂等逻辑。重复确认会返回同一张模拟工单，不会直接创建第二张。

## Trace 事件

复合工作流会写入以下 action_type：

- `plan_created`
- `plan_step_started`
- `plan_step_completed`
- `plan_decision`
- `plan_waiting_confirmation`
- `plan_completed`
- `plan_stopped`

持久化 trace 会脱敏订单号和常见密钥形态，不保存 API Key、完整 Prompt 或真实用户隐私。

## 当前局限

- 只支持 `refund_then_ticket_if_ineligible`，不支持任意任务规划。
- 不是长期记忆，不支持跨用户身份认证。
- 不使用 Redis 或分布式会话；当前使用本地 SQLite 模拟。
- 不执行真实退款、真实取消订单或真实客服系统写入。
- 复合流程只验证工具编排、确认门控和 trace，不代表真实电商平台规则。
