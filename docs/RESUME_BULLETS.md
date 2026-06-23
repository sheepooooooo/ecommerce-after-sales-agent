# 简历描述

## 版本 A：3 条精简版

- 基于 LangGraph 构建电商售后单 Agent 工作流，接入政策 RAG、订单查询、退款资格规则和模拟工单 Tool，实现缺订单号追问、工单显式确认和高风险问题人工处理建议。
- 设计模拟政策知识库与 RAG 检索链路，对比 BM25、BGE + FAISS Dense、Hybrid RRF；Policy QA 使用检索证据包、LLM JSON 输出和引用校验，真实验收 6/6 通过。
- 使用 FastAPI 封装 Agent 服务，补充 request_id、结构化日志、工具耗时、API 验收、稳定性测试和 Docker 配置；全量 pytest 87 passed，受控 Agent 评测各项路由指标为 1.0。

## 版本 B：4 条工程细节版

- 使用 LangGraph StateGraph 实现受控售后 Agent，基于规则基线完成 `policy_qa`、`order_lookup`、`refund_eligibility`、`create_ticket`、`human_handoff` 和 `unknown` 路由。
- 构建模拟售后政策 RAG：Markdown 切块、BM25、BGE Embedding、FAISS IndexFlatIP、Hybrid RRF，并通过引用校验约束 Policy QA 输出。
- 将订单事实存储在 SQLite，退款资格由确定性规则引擎判断，避免 LLM 直接决定退款；模拟工单写入必须显式确认，降低误操作风险。
- 通过 FastAPI、Pydantic、结构化日志、request_id、工具耗时、API 验收、稳定性测试和全量回归脚本提升可测试性；Dockerfile 已配置但当前环境未完成镜像构建验证。
