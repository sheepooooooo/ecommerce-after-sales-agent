# 执行轨迹与可观测性说明

本文档说明当前售后 Agent 的本地模拟执行轨迹能力。它用于学习、调试、评测和面试展示，不是生产级分布式链路追踪系统。

## request_id

`request_id` 是一次 Agent 请求的编号。调用方可以传入，也可以由服务端生成。它用于把一次请求中的节点流转、工具调用、耗时和最终输出串起来。

## execution trace

execution trace 是一次请求的脱敏执行事件列表。每条事件包含：

- `request_id`
- `session_id`
- `step_index`
- `node_name`
- `action_type`
- `tool_name`
- `parameter_summary`
- `result_summary`
- `status`
- `latency_ms`
- `error_category`
- `retry_count`
- `created_at`

重试和降级场景还会记录：

- `action_type=retry_attempt`
- `action_type=retry_success`
- `action_type=retry_exhausted`
- `action_type=fallback`
- `fallback_action`
- `degraded`

当前 trace 存储在 SQLite 的 `agent_trace_events` 表中，可通过 `GET /agent/traces/{request_id}` 查询。

## 为什么记录这些字段

- `node_name`：定位请求走到了哪个 Agent 节点。
- `action_type`：区分节点进入、路由决策、工具结果和最终响应。
- `tool_name`：定位是否调用了订单查询、退款资格、工单创建或政策问答工具。
- `parameter_summary`：只保存脱敏摘要，帮助判断输入是否合理。
- `result_summary`：只保存脱敏、截断后的结果摘要，帮助排查工具返回是否异常。
- `latency_ms`：观察慢请求来自哪个工具或步骤。

## 能定位的问题

- 意图分类错判；
- 缺订单号却错误调用工具；
- 高风险场景没有转人工；
- 工具调用失败；
- 工单创建是否经过确认；
- idempotency key 是否被复用；
- 某个 request_id 是否有完整执行记录。
- LLM 临时异常是否发生重试、重试是否成功、是否进入降级。

## 脱敏边界

当前会对 trace 中的订单号、疑似 API Key、密码、token、验证码和长数字做掩码或替换。`ORD10003` 这类订单号在 trace 摘要中会显示为 `ORD***`。

trace 不应保存或返回：

- API Key、密码、token；
- 验证码；
- 银行卡完整号；
- 完整系统 Prompt；
- 完整原始日志正文。

## 当前局限

- 当前为单机 SQLite 持久化，不是生产级日志平台；
- 没有跨服务分布式 trace；
- 没有采样、保留期、权限系统；
- trace 合法不代表回答语义一定正确；
- 当前仅服务本地模拟订单、模拟工单和离线评测。
- `GET /agent/traces/{request_id}` 仅适用于本地演示环境；真实生产环境还需要鉴权、访问控制、保留期和审计策略。
