# Demo 截图指南

截图前启动命令：

```powershell
python scripts\init_demo_data.py
python scripts\build_all_policy_indexes.py
python -m uvicorn app.api_server:app --host 127.0.0.1 --port 8011
```

打开：

```text
http://127.0.0.1:8011/docs
```

## 1. Swagger 首页和 /health

- 需要展示什么：FastAPI Swagger 页面、`GET /health`、返回 `status=ok`。
- 不应展示什么：`.env`、API Key、终端中的敏感路径或账号信息。
- 截图前命令：启动 API 后访问 `/docs`。
- 面试讲解重点：项目具备本地 API 验收入口，健康检查可用于部署和回归前置验证。

## 2. 订单查询返回：体现 SQLite 订单事实

- 需要展示什么：`POST /agent/run` 请求 `ORD10003 现在是什么状态？`，响应中的 `intent=order_lookup`、`tool_used=order_tool.get_order`、订单状态字段。
- 不应展示什么：真实订单号、真实用户信息。
- 截图前命令：使用 `docs/resume_evidence/demo_requests.json` 中的订单查询请求。
- 面试讲解重点：订单事实来自本地 SQLite 模拟数据，Agent 不凭空生成订单状态。

## 3. 退款资格返回：体现规则引擎结果

- 需要展示什么：请求 `ORD10004 可以退款吗？`，响应中的退款资格判断、理由、下一步建议。
- 不应展示什么：真实退款操作或真实支付信息。
- 截图前命令：使用退款资格请求样例。
- 面试讲解重点：确定性退款资格由规则引擎处理，不交给 LLM 自由判断。

## 4. 工单未确认与确认后创建：体现显式确认

- 需要展示什么：同一工单创建请求在 `confirm_ticket_creation=false` 时返回确认要求，在 `true` 时创建模拟工单。
- 不应展示什么：任何真实售后系统、真实用户身份。
- 截图前命令：分别执行 `创建工单但不确认` 和 `创建工单并确认` 请求样例。
- 面试讲解重点：不可逆或有副作用的动作需要显式确认；当前只创建模拟工单。

## 5. 政策问答返回：体现 RAG 来源引用

- 需要展示什么：请求 `耳机保修多久？`，响应中体现 policy QA、引用来源或工具轨迹。
- 不应展示什么：完整系统 Prompt、完整模型原始响应、API Key。
- 截图前命令：使用政策问答请求样例；如未配置真实 LLM，可展示 live acceptance 报告中的引用校验结果。
- 面试讲解重点：回答受检索证据约束，并做引用合法性校验。
