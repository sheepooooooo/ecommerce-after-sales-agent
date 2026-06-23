# 第四阶段 B：API 设计说明

## 接口列表

### GET /health

用于本地存活检查，不调用 LLM、不读取 API Key、不查询订单数据库。

响应：

```json
{
  "status": "ok",
  "service": "ecommerce-after-sales-agent",
  "version": "0.1.0"
}
```

### POST /agent/run

把现有 LangGraph 单 Agent 封装为 HTTP 接口。

请求：

```json
{
  "user_query": "ORD10004 可以退款吗？",
  "confirm_ticket_creation": false,
  "request_id": null
}
```

响应包含 Agent 原有核心字段，并额外包含：

- `api_latency_ms`
- `agent_latency_ms`
- `request_id`
- `api_version`

响应 Header 包含 `X-Request-ID`。

## request_id 流转

请求进入中间件后，如果 Header 中存在 `X-Request-ID`，优先作为初始请求编号；否则生成 UUID。`POST /agent/run` 的 body 中如果传入 `request_id`，则覆盖 Header 中的值，并继续传给 `run_after_sales_agent()`。最终响应 body 和响应 Header 中保持同一个 request_id。

## 错误码设计

- `validation_error`：请求参数不合法，例如空问题、超长问题、未知字段或布尔类型错误。
- `agent_busy`：进程内 Agent 并发数达到当前配置上限。
- `request_timeout`：Agent 执行超过配置的超时时间。
- `internal_server_error`：未捕获异常，响应中只返回安全的概括提示。

## LangGraph 与 API 的职责边界

API 层负责 HTTP 请求校验、request_id、并发保护、超时控制、依赖注入和结构化日志。LangGraph 仍负责售后任务路由、Tool 调用、缺订单号、工单确认和统一 Agent 响应。订单查询、退款规则、政策问答和工单写入继续由既有 Tool 模块负责。

## 结构化日志字段

日志写入 `logs/agent_api.log`，每行一个 JSON 对象。核心字段包括：

- `timestamp`
- `level`
- `event`
- `request_id`
- `endpoint`
- `http_status`
- `intent`
- `tool_used`
- `answer_status`
- `api_latency_ms`
- `agent_latency_ms`
- `error_code`
- `query_length`
- `masked_order_id`
- `tool_trace`

默认不记录完整用户问题，只记录 `query_length`。订单号脱敏为 `ORD***`。

## 并发保护边界

当前使用 `asyncio.Semaphore` 做进程内基础并发保护，配置项为 `MAX_CONCURRENT_AGENT_REQUESTS`。它不是生产级分布式限流，也不解决多进程、多机器之间的全局并发控制。

## 敏感信息处理原则

日志和报告不得记录 API Key、密码、验证码、银行卡完整号码、完整 Prompt 或完整证据包。当前服务只创建本地模拟工单，不执行真实退款、真实取消订单或真实售后动作。
