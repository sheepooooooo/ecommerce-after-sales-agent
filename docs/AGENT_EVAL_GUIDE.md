# 售后 Agent 自动化评测指南

本文档说明当前 `ecommerce_after_sales_agent` 的离线 Agent 评测设计。评测目标是重复验证路由、工具调用、实体抽取、结构化输出和安全门控，不替代真实用户体验评审，也不宣称线上准确率。

## 评测集设计

评测数据位于 `eval/after_sales_agent_eval_questions.jsonl`，每条样本包含：

- `id`：稳定样本编号。
- `category`：评测分类。
- `query`：模拟用户问题，不包含真实用户信息。
- `expected_intent`：期望意图。
- `expected_status`：期望业务状态。
- `expected_tool`：期望 Tool；不应调用工具时为 `null`。
- `expected_order_id` / `expected_order_ids`：期望抽取出的订单号。
- `expected_route`：期望图路径或业务节点。
- `expected_safety`：安全门控预期，例如不写库、不调用退款 Tool、必须转人工。
- `notes`：样本验证目的或已知边界说明。
- `conversation_steps`：可选，多轮会话样本使用；每一步都包含独立 query、期望状态和安全门控。

当前分类覆盖：

- `policy_qa`：保修、优惠券、支付、发票、积分、发货、拒收等政策问答。
- `order_lookup`：正常订单查询、小写订单号、多订单号、不存在订单号、缺订单号。
- `refund_eligibility`：未支付、已支付未发货、已发货未签收、已签收 7 天内、质量问题、已拆封、超期、已退款等规则判断。
- `ticket_safety`：未确认不写库、确认后写入隔离库、缺订单号、模糊确认等工单安全场景。
- `ticket_safety` 中包含真实多轮确认样本，例如创建后确认、创建后取消、无 pending 确认、会话隔离和重复确认。
- `controlled_workflow`：受控复合任务样本，例如“先判断退款资格；若不可直接退款，再进入工单确认”。该分类会额外校验 `workflow_summary`、trace 中的 plan 事件和写库门控。
- `multi_turn_resume`：缺订单号后的任务续办样本，例如退款资格、订单查询、创建工单、复合任务、取消、中断和会话隔离。
- `high_risk_handoff`：重复扣款、银行卡、账号安全、隐私泄露、强投诉等高风险人工兜底。
- `unrelated_colloquial`：天气、闲聊、口语化退货、多意图混合和真实 badcase。

## 指标定义

`scripts/evaluate_after_sales_agent.py` 会输出以下核心指标：

- `intent_accuracy`：实际意图是否等于期望意图。
- `route_or_status_accuracy`：实际路径和 `answer_status` 是否符合预期。
- `tool_selection_accuracy`：应该调用的 Tool 是否被调用，不该调用时是否未调用。
- `entity_extraction_accuracy`：订单号抽取是否符合期望；多订单号会校验完整列表。
- `safety_gate_pass_rate`：安全门控是否满足预期，包括未确认不写库、高风险不调用写操作、缺订单号不调用高风险 Tool。
- `response_schema_valid_rate`：Agent 输出是否符合 `AfterSalesAgentResponse` 结构，且关键字段类型正确。
- `end_to_end_success_rate`：一条样本所有适用检查项都通过才算端到端成功。
复合工作流样本还会读取 `expected_workflow`，校验 `workflow_type`、`plan_status`、`next_action` 等结构化字段。该检查只验证受控编排状态，不评价自然语言措辞。

报告还会按 `category` 输出样本数和通过率，并按失败类型聚合 Top badcases。

## 如何运行

在项目根目录执行：

```powershell
python scripts\evaluate_after_sales_agent.py
```

运行后会生成：

- `eval_results/after_sales_agent_eval_results.jsonl`
- `eval_results/after_sales_agent_eval_summary.json`
- `eval_results/after_sales_agent_eval_report.md`
- `eval_results/after_sales_agent_badcases.md`

`eval_results/` 是本地运行产物，已被 `.gitignore` 忽略。

## 评测模式

该评测不调用真实 DeepSeek 或其他外部 LLM。政策问答路径使用本地 stub，原因是当前阶段需要稳定验证 Agent 编排，而不是让自然语言生成波动影响路由和安全指标。

工单创建评测使用临时 SQLite 数据库。脚本会在临时目录初始化一份模拟订单库，确认写库样本只写入隔离库，脚本结束后自动清理，不污染 `data/orders.db`。

多轮会话评测同样使用这份隔离 SQLite。第一轮保存 pending action，后续步骤通过上一轮返回的 `session_id` 恢复状态，验证真实两轮确认和缺订单号后的任务续办，而不是单请求布尔参数。

## 自动评测边界

政策问答不会用“答案全文字符串完全一致”判分。原因是自然语言答案可以有多种合格表达，简单字符串匹配会把正确但措辞不同的回答误判为失败。

当前自动评测只检查政策问答是否：

- 路由到政策问答路径；
- 输出预期状态；
- 保留引用和证据结构；
- 通过响应 schema 校验。

政策答案是否完整、语气是否合适、是否严格覆盖用户问题，仍需要人工复核或后续更细粒度的可解释评测。引用合法也不代表答案语义绝对正确。

## Badcase 处理原则

评测集中允许保留当前规则分类器覆盖不到的真实 badcase，例如泛化发货时效问法、缺订单号创建工单的路由顺序、包含“订单没关系”的闲聊误判。

这些失败不应通过删除样本或修改预期来消除。后续若要提升指标，应在明确需求后改进分类器、图路由或提示策略，并保留回归样本。

## 第三阶段增量：trace 与幂等

评测集中新增 `observability` 类样本，用于验证：

- Agent 请求是否写入可按 `request_id` 查询的持久化 trace；
- trace 是否包含必要结构化字段；
- trace 摘要是否避免暴露完整订单号、密钥、密码、验证码等敏感片段；
- 不存在的 `request_id` 查询应返回未命中结果。

`ticket_safety` 类样本新增幂等相关场景，用于验证：

- 同一 session 重复确认时不会重复创建工单；
- 相同 `idempotency_key` 重复提交时返回已有 `ticket_id`；
- 不同 session 与不同 key 的合法写操作不会串用结果。

这些检查仍然是离线规则判分，不评价自然语言答案文案优劣，也不调用真实 LLM。

## 第四阶段增量：重试与降级

评测集中新增 `retry_and_degradation` 类样本，用于验证：

- LLM 首次临时失败后重试成功；
- LLM 连续失败后返回 `degraded`，不编造政策答案；
- 业务结果如缺订单号、未确认创建工单、订单不存在不触发重试；
- retry / fallback 事件进入持久化 trace。

评测报告中的核心指标同时输出：

- `passed_count`：通过样本数；
- `applicable_count`：该指标适用样本数；
- `rate`：通过率。

部分指标不是所有样本都适用，例如政策引用校验只适用于政策问答，安全门控只适用于写库或高风险样本，因此分母可能小于总样本数。

## 第五阶段增量：多轮信息补全与任务续办

评测集中新增 `multi_turn_resume` 类样本，用于验证：

- `refund_eligibility` 缺订单号后，同一 session 补订单号会恢复退款资格判断；
- `order_lookup` 缺订单号后，同一 session 补订单号会恢复订单查询；
- `create_ticket` 缺订单号后，补订单号只进入确认，不直接写库；
- `refund_then_ticket_if_ineligible` 缺订单号后，补订单号继续受控复合流程；
- 用户取消会清理 pending，不调用工具；
- 用户发起新的明确业务请求会中断旧 pending，并记录 `pending_task_interrupted`；
- 不同 session 之间不会串用 pending 状态。

该分类仍不调用真实 LLM，所有写库检查都在隔离 SQLite 中完成。
