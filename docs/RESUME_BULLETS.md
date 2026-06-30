# 简历描述

## 精简版

- 基于 LangGraph 构建本地模拟电商售后 Agent，整合政策 RAG、订单查询、退款资格规则引擎、显式确认工单 Tool、高风险人工兜底和一个受控复合工作流 `refund_then_ticket_if_ineligible`。
- 设计模拟政策知识库与 RAG 检索链路，对比 BM25、BGE + FAISS Dense、Hybrid RRF；Policy QA 使用检索证据包、LLM JSON 输出和引用校验，固定真实验收 6/6 通过。
- 使用 FastAPI 封装 Agent 服务，补充 `request_id`、`session_id`、幂等键、脱敏 trace、重试降级和结构化响应；离线 Agent 评测 79 条，端到端 77/79，安全门控 79/79，pytest 129 passed。

## 工程细节版

- 将 LLM 能力限制在政策问答链路，退款资格由确定性规则引擎基于 SQLite 订单事实判断，避免模型直接决定退款或写库。
- 对模拟工单创建加入缺订单号续办、真实两轮确认、SQLite session 持久化和 `idempotency_key` 保护，重复确认返回同一 `ticket_id`。
- 为 Agent 运行链路保存脱敏 trace，覆盖节点进入、工具结果、复合工作流 plan 事件、retry/fallback 和最终响应，支持按 `request_id` 查询。
- 扩展离线评测器，覆盖意图、路径/状态、工具选择、订单号抽取、安全门控、响应 schema、复合工作流状态和端到端成功率；保留 ASAE007、ASAE016 作为真实 badcase。

## 使用边界

以上描述只适用于本地模拟项目。订单、政策和工单均为模拟数据；项目不执行真实退款、真实取消订单、真实物流修改或真实客服动作；CI 不调用真实 LLM。
