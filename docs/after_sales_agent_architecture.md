# 第四阶段 A：LangGraph 多工具售后 Agent 架构

## 业务目标

本阶段把既有政策问答、订单查询、退款资格判断和模拟工单能力接入一个受控 LangGraph StateGraph。Agent 只负责识别意图、提取订单号、选择 Tool、处理缺订单号和工单确认分支，并输出统一结构。

## 模块边界

- `app/agent/entity_extractor.py`：用正则提取 `ORD + 5 位数字` 的订单号。
- `app/agent/intent_classifier.py`：规则基线意图分类，不调用 LLM。
- `app/agent/after_sales_graph.py`：LangGraph 节点、条件边和 Tool 调用。
- `app/agent/response_formatter.py`：统一格式化响应。
- `app/tools/*`：继续承载订单查询、工单创建、退款资格和政策问答业务能力。

## Agent State 字段说明

State 只描述一次请求在节点间传递的信息，不是长期 Memory。核心字段包括：

- `request_id`：请求编号。
- `user_query`：用户原始问题。
- `confirm_ticket_creation`：是否显式确认创建模拟工单。
- `order_id` / `all_detected_order_ids`：第一个订单号和全部匹配订单号。
- `intent` / `intent_reason` / `requires_order_id`：意图分类结果。
- `tool_used` / `tool_trace`：工具选择和节点轨迹。
- `policy_qa_result` / `order_result` / `refund_result` / `ticket_result`：各 Tool 的结构化结果。
- `answer_status` / `answer` / `citations`：统一回答状态、文本和引用。
- `needs_human_review` / `confirmation_required`：人工处理和确认标志。
- `error` / `debug`：错误与调试信息，不保存 API Key 或完整系统 Prompt。

## LangGraph 节点与条件边

固定链路为：

```text
START -> receive_request_node -> extract_entities_node -> classify_intent_node
```

之后通过条件边路由：

- `policy_qa` -> `policy_qa_node` -> `format_response_node` -> END
- `order_lookup` 且无订单号 -> `ask_for_order_id_node` -> `format_response_node` -> END
- `order_lookup` 且有订单号 -> `order_lookup_node` -> `format_response_node` -> END
- `refund_eligibility` 且无订单号 -> `ask_for_order_id_node` -> `format_response_node` -> END
- `refund_eligibility` 且有订单号 -> `refund_eligibility_node` -> `format_response_node` -> END
- `create_ticket` 且未确认 -> `ticket_confirmation_node` -> `format_response_node` -> END
- `create_ticket` 且已确认 -> `create_ticket_node` -> `format_response_node` -> END
- `human_handoff` -> `human_handoff_node` -> `format_response_node` -> END
- `unknown` -> `unknown_node` -> `format_response_node` -> END

## 不同意图的调用链

- 政策咨询：调用 `policy_qa_tool.ask_policy_question`，保留引用和 grounding verification。
- 订单查询：调用 `order_tool.get_order`，只返回必要订单状态字段。
- 退款资格：调用 `refund_eligibility_tool.check_refund_eligibility`，复用订单事实和规则引擎。
- 工单创建：只有 `confirm_ticket_creation=True` 时调用 `order_tool.create_ticket`。
- 人工处理和未知请求：不调用 LLM，不写数据库。

## 工单确认安全机制

创建工单会写入本地 SQLite 模拟数据库，因此默认只返回 `ticket_confirmation_required`。只有调用服务时显式传入 `confirm_ticket_creation=True`，图才会进入 `create_ticket_node`。

## 为什么退款判断不由 LLM 决定

退款资格依赖支付状态、发货状态、签收时间、拆封情况和质量问题等结构化事实。此类结论需要稳定、可测试、可复现，因此由规则引擎输出。LLM 可以辅助解释政策，但不能替代确定性退款判断。

## 评测指标

离线评测统计：

- `total_questions`
- `intent_accuracy`
- `tool_selection_accuracy`
- `order_id_extraction_accuracy`
- `missing_order_id_handling_accuracy`
- `ticket_confirmation_safety_accuracy`
- `success_rate`

## 当前局限

- 意图路由仍是规则基线，不是 LLM 路由。
- 当前是单 Agent、受控图工作流，不是多 Agent。
- 不实现 FastAPI、前端、Memory、MCP 或网页搜索。
- 政策问答可调用真实 LLM，但离线评测默认使用 stub。
- 工单、订单和政策均为模拟数据，仅用于学习演示。
