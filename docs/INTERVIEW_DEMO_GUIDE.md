# 面试 Demo 指南

本文用于 5 分钟现场演示。演示目标是让面试官快速看到：项目不是简单聊天 Demo，而是一个可测试、可追踪、有安全门控的本地模拟售后 Agent。

## 演示前准备

```powershell
python scripts\init_demo_data.py
python scripts\build_all_policy_indexes.py
```

如需启动 API：

```powershell
python -m uvicorn app.api_server:app --host 127.0.0.1 --port 8011 --reload
```

## 5 分钟顺序

1. 项目定位，30 秒  
   本地模拟电商售后 Agent，订单、政策、工单均为模拟数据。LLM 只用于政策问答，不决定退款或写库。

2. 政策问答，60 秒  
   演示问题：`耳机买了以后一般保修多长时间？`  
   关注点：RAG 检索、引用校验、JSON 输出。若现场没有真实 API Key，可说明 pytest 和离线评测使用 stub，真实 LLM 验收由 `run_policy_qa_live_acceptance.py` 手动运行。

3. 退款资格判断，60 秒  
   演示问题：`ORD10004 可以直接退款吗？`  
   关注点：订单事实来自 SQLite，退款结论来自确定性规则引擎，不由 LLM 猜测。

4. 复合任务进入工单确认，90 秒  
   演示问题：`ORD10003 能退款吗？如果不能，帮我创建售后工单。`  
   关注点：系统先判断退款资格；不可直接退款时只返回 `ticket_confirmation_required`，不立即写库。

5. 重复确认幂等与 trace 查询，60 秒  
   同一 `session_id` 输入 `确认` 创建模拟工单，再次确认返回同一 `ticket_id`。用 `/agent/traces/{request_id}` 或 Demo 脚本展示脱敏 trace。

## 推荐命令

```powershell
python scripts\demo_after_sales_agent.py
python scripts\evaluate_after_sales_agent.py
```

API Demo：

```powershell
python scripts\demo_api_requests.py
```

## 四个关键场景

- 政策问答：验证检索、引用和 LLM 受证据约束。
- 退款资格：验证规则引擎与订单事实。
- 受控复合任务：验证 `refund_then_ticket_if_ineligible` 的固定编排。
- 幂等与 trace：验证写安全和可观测性。

## 面试时必须说明的边界

- 项目不是生产级系统，没有真实用户鉴权和线上高可用。
- 当前离线 Agent 评测为 71 条，端到端通过 69 条，保留 ASAE007、ASAE016 badcase。
- CI 只运行 pytest，不调用真实 LLM，也不代表线上模型稳定性。
- 本项目不执行真实退款、真实订单取消或真实客服工单。
- 不包含 Multi-Agent、MCP、Redis、长期记忆、复杂前端或自由 ReAct 循环。
