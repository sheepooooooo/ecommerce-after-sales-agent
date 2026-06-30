# ecommerce_after_sales_agent

本项目是一个本地模拟电商售后 Agent，用于展示 RAG 政策问答、确定性退款规则、LangGraph 工具编排、显式确认写库、幂等保护、trace 观测和离线评测闭环。

它不是生产级系统，不代表任何真实电商平台政策，不执行真实退款、真实取消订单、真实物流修改或真实客服工单。

## 业务问题

电商售后场景里，用户问题常常混合了政策咨询、订单查询、退款资格判断和工单创建诉求。本项目把这些动作拆成可验证的工程模块：

- 政策类问题走 RAG Policy QA，LLM 只基于检索到的模拟政策回答；
- 订单和退款资格走 SQLite 与确定性规则引擎；
- 写入模拟工单前必须经过显式确认；
- 高风险问题直接人工兜底，不调用退款或写库工具；
- 复合请求只支持一个受控流程：`refund_then_ticket_if_ineligible`。

## 核心能力

- Policy QA：BM25 / Dense / Hybrid 检索，DeepSeek JSON 输出，引用合法性校验。
- 订单查询：从本地 SQLite 查询模拟订单事实。
- 退款资格判断：由规则引擎基于订单事实判断，不交给 LLM 猜测。
- 模拟工单：创建前需要确认，支持 `session_id` 多轮信息补全、确认恢复和 `idempotency_key` 幂等。
- 受控复合流程：先判断退款资格，不可直接退款且用户要求兜底时，再进入工单确认。
- 可观测性：`request_id`、`tool_trace`、工具耗时、持久化 trace、错误分类、重试与降级。
- 自动化评测：离线 Agent 评测集 79 条，pytest 与 full checks 可重复运行。

## 架构图

```text
User / API
   |
   v
FastAPI /agent/run
   |
   v
AfterSalesAgentService
   |-- session_store: pending_action / session_id
   |-- idempotency_store: duplicate write protection
   |-- trace_store: sanitized execution trace
   |
   v
LangGraph after_sales_graph
   |-- intent_classifier
   |-- policy_qa_tool ----------------> RAG + optional DeepSeek
   |-- order_tool --------------------> SQLite simulated orders/tickets
   |-- refund_eligibility_tool -------> deterministic refund_rule_engine
   |-- controlled workflow -----------> refund_then_ticket_if_ineligible
   |
   v
Structured JSON response
```

## 请求数据流

1. API 或脚本传入 `user_query`，可选传入 `session_id`、`request_id`、`idempotency_key`。
2. Agent 抽取订单号并进行规则意图分类。
3. 根据意图进入政策问答、订单查询、退款资格、工单确认或人工兜底路径。
4. 缺订单号时会把受控任务保存到短期 session；同一 `session_id` 补充订单号后续办原任务。
5. 所有写工单动作必须满足确认条件，并经过幂等保护。
6. 响应中返回结构化字段、`session_id`、`tool_trace` 和调试摘要。
7. trace 会脱敏保存，可通过 `/agent/traces/{request_id}` 查询。

## 受控复合任务

当前只支持一个复合工作流：

```text
用户：ORD10003 能退款吗？如果不能，帮我创建售后工单。
  -> 查询订单
  -> 判断退款资格
  -> 若可退款：直接回答，不创建工单
  -> 若不可直接退款：返回 ticket_confirmation_required
  -> 用户同一 session 输入“确认”
  -> 创建本地模拟工单，并记录幂等结果
```

该流程不是自由 ReAct 循环，不允许 LLM 自主选择写库工具，也不会自动退款。

## Session、Trace、幂等、重试与降级

- `session_id`：保存短期 pending action，用于缺订单号后的任务续办和真实两轮确认，不是长期记忆。
- `trace`：保存脱敏后的执行轨迹，便于排查路由、工具调用、错误分类和耗时。
- `idempotency_key`：重复确认或重复提交时返回同一个模拟工单，避免重复写库。
- 重试与降级：仅用于政策问答中的只读 LLM 调用；工单写库、退款规则、缺订单号等业务结果不自动重试。

## API 列表

| Method | Endpoint | 说明 |
|---|---|---|
| GET | `/health` | 服务健康检查 |
| POST | `/agent/run` | 运行售后 Agent |
| GET | `/agent/traces/{request_id}` | 查询脱敏执行 trace |

Swagger:

```text
http://127.0.0.1:8011/docs
```

## Windows PowerShell 快速启动

```powershell
python -m pip install -r requirements.txt
python scripts\init_demo_data.py
python scripts\build_all_policy_indexes.py
python -m uvicorn app.api_server:app --host 127.0.0.1 --port 8011 --reload
```

另开终端运行 API Demo：

```powershell
python scripts\demo_api_requests.py
```

本地 Agent Demo：

```powershell
python scripts\demo_after_sales_agent.py
```

## Demo 与验证命令

```powershell
python scripts\demo_after_sales_agent.py
python scripts\evaluate_after_sales_agent.py
python -m pytest -q
python scripts\run_full_checks.py
```

真实 Policy QA 模型验收需要本地 `.env` 中配置 API Key，且不纳入 CI：

```powershell
python scripts\check_llm_connection.py
python scripts\run_policy_qa_live_acceptance.py
```

## 离线评测结果

最近一次本地离线 Agent 评测结果：

| 指标 | 通过数 / 适用总数 | 比率 |
|---|---:|---:|
| 总样本 | 77 / 79 | 0.9747 |
| intent_accuracy | 76 / 78 | 0.9744 |
| route_or_status_accuracy | 77 / 79 | 0.9747 |
| tool_selection_accuracy | 77 / 78 | 0.9872 |
| entity_extraction_accuracy | 78 / 78 | 1.0000 |
| safety_gate_pass_rate | 79 / 79 | 1.0000 |
| response_schema_valid_rate | 79 / 79 | 1.0000 |
| end_to_end_success_rate | 77 / 79 | 0.9747 |
| controlled_workflow | 9 / 9 | 1.0000 |
| multi_turn_resume | 8 / 8 | 1.0000 |

评测模式说明：这是受控离线评测，政策问答使用 stub，不调用真实 LLM；写工单样本使用隔离 SQLite，不污染 `data/orders.db`。这些指标不代表线上准确率或真实用户场景泛化能力。

当前保留两个真实 badcase：`ASAE007`、`ASAE016`，详见 [docs/BADCASE_ANALYSIS.md](docs/BADCASE_ANALYSIS.md)。

## 项目目录

```text
app/
  agent/          LangGraph 工作流、意图分类、响应格式化
  api/            FastAPI schema、依赖和异常处理
  llm/            DeepSeek client
  retrieval/      政策加载、BM25/Dense/Hybrid 检索
  services/       规则引擎、session、幂等、trace、重试
  tools/          可调用业务工具
data/
  policies/       模拟政策 Markdown
eval/             离线评测集
scripts/          初始化、构建索引、Demo、评测和检查脚本
tests/            pytest 自动化测试
docs/             架构、Demo、评测、badcase 和发布说明
```

## 详细文档

- [项目概览](docs/PROJECT_OVERVIEW.md)
- [面试 Demo 指南](docs/INTERVIEW_DEMO_GUIDE.md)
- [最终验证记录](docs/FINAL_VERIFICATION.md)
- [受控复合工作流](docs/CONTROLLED_WORKFLOW_ORCHESTRATION.md)
- [Agent 评测指南](docs/AGENT_EVAL_GUIDE.md)
- [多轮 Session 设计](docs/MULTI_TURN_SESSION_DESIGN.md)
- [多轮信息补全与任务续办](docs/MULTI_TURN_WORKFLOW_RESUME.md)
- [Trace 与可观测性](docs/OBSERVABILITY_AND_TRACE.md)
- [幂等与写安全](docs/IDEMPOTENCY_AND_WRITE_SAFETY.md)
- [重试与降级](docs/RETRY_AND_DEGRADATION.md)
- [Badcase 分析](docs/BADCASE_ANALYSIS.md)

## 安全说明

- 不提交 `.env`、`.env.*`，但保留 `.env.example`。
- 不提交本地 SQLite 数据库、日志、索引和 `eval_results/`。
- 不在代码、README、测试或日志中写入 API Key。
- 本项目不处理真实支付、真实用户隐私、真实订单或真实售后动作。
- GitHub Actions CI 只安装依赖并运行 pytest，不依赖真实 API Key，也不调用真实 LLM。

## 已知局限

- 不是生产级系统，没有真实鉴权、权限模型、分布式限流、高可用或监控平台。
- 当前仅支持一个受控复合工作流，不支持自由任务规划。
- 退款资格由模拟规则判断，不代表真实平台政策或法律意见。
- LLM 只用于政策问答链路，且引用合法不等于答案语义绝对正确。
- Dockerfile 可用于展示配置，但本项目当前发布版不声明已经完成线上部署验证。
