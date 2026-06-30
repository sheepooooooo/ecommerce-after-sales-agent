# 项目概览

`ecommerce_after_sales_agent` 是一个本地模拟电商售后 Agent 项目。它用模拟订单、模拟政策和模拟工单展示 AI 应用开发中常见的工程问题：RAG 问答如何可溯源，业务判断如何避免交给 LLM 猜测，写操作如何加确认、幂等和 trace。

## 架构

```text
FastAPI / Scripts
  -> AfterSalesAgentService
      -> session_store / idempotency_store / trace_store
      -> LangGraph after_sales_graph
          -> intent_classifier
          -> policy_qa_tool
          -> order_tool
          -> refund_eligibility_tool
          -> controlled_workflow
```

## 核心模块职责

- `app/agent/`：售后 Agent 图、意图分类、实体抽取和响应格式化。
- `app/tools/`：可被 Agent 调用的业务工具，包括订单查询、退款资格和政策问答工具。
- `app/services/`：规则引擎、会话状态、幂等记录、trace、错误分类和重试降级。
- `app/retrieval/`：模拟政策加载、切块、BM25/Dense/Hybrid 检索。
- `app/api_server.py` 与 `app/api/`：FastAPI 服务和请求响应 schema。
- `data/policies/`：模拟政策文档，不代表真实平台政策。
- `eval/` 与 `scripts/evaluate_after_sales_agent.py`：离线评测集与自动判分脚本。

## 数据流

1. 用户输入售后问题。
2. 系统抽取订单号，并通过规则分类器识别意图。
3. 政策问题进入 RAG 问答；订单问题进入 SQLite 查询；退款问题进入规则引擎。
4. 缺少订单号时，系统把有限受控任务保存到短期 session；同一 `session_id` 补充订单号后续办原任务。
5. 工单创建必须经过显式确认，并通过 `idempotency_key` 防止重复写入。
6. 每次请求保存脱敏 trace，便于复盘工具调用路径。

## 设计取舍

- 退款资格不用 LLM 判断，而使用确定性规则引擎，保证可测试和可解释。
- 政策问答允许调用 LLM，但必须基于检索证据，并校验引用是否合法。
- 当前只支持一个受控复合工作流：`refund_then_ticket_if_ineligible`，避免自由 Agent 随意写库。
- 会话状态存在 SQLite，只用于缺订单号续办和短期确认，不是长期记忆。
- 离线评测不使用 LLM-as-a-Judge，优先校验路由、工具、实体、schema 和安全门控。

## 与普通聊天机器人或纯 RAG 的区别

普通聊天机器人常把所有问题交给模型生成答案；本项目把售后动作拆成可验证的工具和状态流。纯 RAG 只能回答政策，本项目还能查询模拟订单、调用退款规则、处理确认写库、记录 trace，并对这些行为做离线自动评测。

## 边界

本项目是本地模拟系统。它不处理真实用户数据，不执行真实退款或真实客服操作，不声明 production-ready，也不把 CI 结果解释为线上 LLM 稳定性验证。
