# API 验收说明

## 为什么 API 验收与 pytest 不同

pytest 使用 FastAPI TestClient 在进程内测试接口行为，不需要真实启动 Uvicorn。`scripts/run_api_checks.py` 会启动本地 Uvicorn 子进程，并通过真实 HTTP 请求验证服务启动、Header、路由和响应结构。

## 为什么 run_api_checks.py 不测试真实 LLM

真实 LLM 依赖 `.env` 中的 `DEEPSEEK_API_KEY`，会引入网络、密钥和模型稳定性因素。本阶段 API 验收重点是服务化、request_id、结构化响应、无 LLM 路径和工单确认安全机制，因此脚本只覆盖订单查询、退款判断、缺订单号、工单确认、人工处理和 unknown。

## 如何启动服务

```powershell
python scripts\init_demo_data.py
python scripts\build_all_policy_indexes.py
python -m uvicorn app.api_server:app --host 127.0.0.1 --port 8011 --reload
```

## 如何使用 Swagger

启动服务后访问：

```text
http://127.0.0.1:8011/docs
```

## 如何查看日志

API 日志写入：

```text
logs/agent_api.log
```

日志是 JSON Lines 格式，每行一条结构化事件。默认只记录用户问题长度和脱敏订单号。

## 常见错误排查

- 端口被占用：停止已有 8011 服务后重试。
- 422 validation_error：检查 `user_query` 是否为空、过长，或请求体是否包含未知字段。
- 503 agent_busy：当前进程内 Agent 请求达到配置上限，稍后重试。
- 504 request_timeout：Agent 执行超过配置时间，检查本地模型、索引或外部 LLM 是否过慢。
- policy_qa 失败：检查 `.env` 是否配置 `DEEPSEEK_API_KEY`；该失败不影响订单、退款、工单和人工处理路径。
