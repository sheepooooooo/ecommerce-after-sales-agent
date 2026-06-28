# 项目总结

`ecommerce_after_sales_agent` 是一个面向 AI 应用 / Agent 岗位展示的本地模拟电商售后 Agent。它把政策问答、订单查询、退款资格判断、模拟工单创建、显式确认、幂等保护和 trace 观测整合到一个可测试的工程项目中。

## 当前实现

- RAG 政策问答：基于模拟政策文档检索，支持引用校验；真实 LLM 调用仅用于政策问答链路。
- 订单查询：从本地 SQLite 查询模拟订单。
- 退款资格：由确定性规则引擎判断，不交给 LLM 决定。
- 工单创建：必须经过显式确认，支持 session 恢复和幂等保护。
- 受控复合工作流：当前只支持 `refund_then_ticket_if_ineligible`。
- FastAPI：提供 `/health`、`/agent/run`、`/agent/traces/{request_id}`。
- 可观测性：记录 request_id、tool_trace、工具耗时、错误分类、retry/fallback 和脱敏持久化 trace。
- 自动化验证：pytest、Agent 离线评测、API 验收、稳定性测试和 full checks。

## 技术栈

- Agent 编排：LangGraph StateGraph
- API：FastAPI、Pydantic
- 检索：BM25、BGE Embedding、FAISS、Hybrid RRF
- LLM：DeepSeek API，OpenAI 兼容客户端
- 数据：SQLite、本地 Markdown 政策、本地索引文件
- 测试与评测：pytest、JSONL 离线评测、PowerShell 运行脚本

## 当前指标

当前受控离线 Agent 评测集共 71 条，端到端通过 69 条。

| 指标 | 通过数 / 适用总数 | 比率 |
|---|---:|---:|
| intent_accuracy | 68 / 70 | 0.9714 |
| route_or_status_accuracy | 69 / 71 | 0.9718 |
| tool_selection_accuracy | 69 / 70 | 0.9857 |
| entity_extraction_accuracy | 70 / 70 | 1.0000 |
| safety_gate_pass_rate | 71 / 71 | 1.0000 |
| response_schema_valid_rate | 71 / 71 | 1.0000 |
| end_to_end_success_rate | 69 / 71 | 0.9718 |
| controlled_workflow | 9 / 9 | 1.0000 |

保留 ASAE007、ASAE016 两个真实 badcase，详见 `docs/BADCASE_ANALYSIS.md`。

## 项目边界

- 所有订单、政策、工单均为模拟数据。
- 不执行真实退款、真实取消订单、真实物流修改或真实客服动作。
- 当前不是生产级系统，没有真实用户鉴权、权限模型、高可用和监控平台。
- CI 只运行本地 pytest，不调用真实 LLM，不代表线上模型稳定性。
- Dockerfile 可展示容器化配置，但当前发布版不声明已经完成线上部署验证。

## 适合展示的亮点

- 将 LLM 问答与确定性业务规则清晰分层。
- 对写操作使用显式确认和幂等保护。
- 用离线评测集度量路由、工具选择、实体抽取、schema 和安全门控。
- 保留 badcase，展示真实工程取舍和可迭代空间。
