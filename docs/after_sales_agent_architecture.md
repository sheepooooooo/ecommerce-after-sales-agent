# 售后 Agent 架构说明

本文记录当前最终发布版的售后 Agent 架构。更适合 GitHub 首页阅读的摘要见 `README.md`，面试演示路径见 `docs/INTERVIEW_DEMO_GUIDE.md`。

## 模块边界

- `app/agent/entity_extractor.py`：抽取 `ORD` 订单号。
- `app/agent/intent_classifier.py`：规则意图分类，不调用 LLM。
- `app/agent/after_sales_graph.py`：LangGraph 节点、条件边、工具调用和受控复合流程。
- `app/agent/after_sales_agent_service.py`：服务入口，协调 session、幂等和 trace。
- `app/tools/`：订单、退款资格、政策问答等可调用业务工具。
- `app/services/`：退款规则、Policy QA、session、幂等、trace、重试和错误分类。
- `app/api_server.py`：FastAPI HTTP 服务。

## LangGraph 主路径

```text
START
  -> receive_request_node
  -> extract_entities_node
  -> classify_intent_node
  -> conditional route
       -> policy_qa_node
       -> order_lookup_node
       -> refund_eligibility_node
       -> ticket_confirmation_node
       -> create_ticket_node
       -> refund_then_ticket_workflow_node
       -> human_handoff_node
       -> unknown_node
  -> format_response_node
  -> END
```

## 受控复合流程

`refund_then_ticket_if_ineligible` 只支持一个固定计划：

```text
extract_order_id
  -> lookup_order
  -> check_refund_eligibility
  -> decide_ticket_fallback
```

当订单可退款时，流程直接回答并结束；当不可直接退款且用户明确要求工单兜底时，流程只保存待确认动作，不直接写库。用户在同一 `session_id` 中输入“确认”后，才复用普通工单创建节点。

## 安全边界

- 退款资格由确定性规则引擎判断，不由 LLM 决定。
- 工单创建写入本地模拟 SQLite，必须显式确认。
- 高风险问题不调用 LLM、不调用退款 Tool、不写工单。
- trace 会脱敏订单号和常见密钥形态。
- 当前不是生产级系统，不包含 Multi-Agent、MCP、Redis、长期记忆、复杂前端或自由 ReAct 循环。

## 评测口径

当前 Agent 离线评测集为 79 条，端到端通过 77 条；`controlled_workflow` 分类 9/9 通过，`multi_turn_resume` 分类 8/8 通过。ASAE007、ASAE016 保留为真实 badcase。
