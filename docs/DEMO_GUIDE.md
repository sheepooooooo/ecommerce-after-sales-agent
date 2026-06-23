# Demo Guide

## 3 分钟面试演示脚本

### 1. Swagger /health

- 输入：打开 `http://127.0.0.1:8011/docs`，调用 `GET /health`。
- 预期路由：FastAPI health endpoint。
- 调用工具：无。
- 关键输出：`status=ok`、服务名和版本。
- 强调点：健康检查不调用 LLM、不读 API Key、不查数据库。

### 2. ORD10003 查询订单状态

- 输入：`ORD10003 现在是什么状态？`
- 预期路由：`order_lookup`
- 调用工具：`order_tool.get_order`
- 关键输出：商品名、支付状态、物流状态、退款状态。
- 强调点：订单查询基于 SQLite 事实，不由 LLM 猜测。

### 3. ORD10004 退款资格判断

- 输入：`ORD10004 可以退款吗？`
- 预期路由：`refund_eligibility`
- 调用工具：`refund_eligibility_tool.check_refund_eligibility`
- 关键输出：`eligible`、`refund_type`、`reason`、`next_action`。
- 强调点：退款结论来自订单事实和规则引擎。

### 4. “我想退款”缺订单号追问

- 输入：`我想退款`
- 预期路由：`refund_eligibility -> missing_order_id`
- 调用工具：无。
- 关键输出：提示提供 `ORD10003` 格式订单号。
- 强调点：缺订单号时不调用订单或退款 Tool。

### 5. 创建工单未确认

- 输入：`请创建工单，订单号是 ORD10003`
- 预期路由：`create_ticket -> ticket_confirmation`
- 调用工具：无。
- 关键输出：`ticket_confirmation_required`
- 强调点：写数据库动作必须显式确认。

### 6. 确认后创建模拟工单

- 输入：同上，`confirm_ticket_creation=true`
- 预期路由：`create_ticket`
- 调用工具：`order_tool.create_ticket`
- 关键输出：模拟工单编号。
- 强调点：当前只写入本地模拟工单，不是真实客服系统。

### 7. “银行卡重复扣款”人工处理建议

- 输入：`我的银行卡被重复扣款了`
- 预期路由：`human_handoff`
- 调用工具：无。
- 关键输出：建议人工处理，并提示不要提供密码、验证码、银行卡完整号。
- 强调点：高风险问题不调用 LLM、不写数据库。

### 8. “耳机保修多久”政策 RAG 问答与引用

- 输入：`耳机保修多久？`
- 预期路由：`policy_qa`
- 调用工具：`policy_qa_tool.ask_policy_question`
- 关键输出：保修期限、citations、grounding verification。
- 强调点：政策问答可调用 LLM，但回答受检索证据和引用校验约束。

## 7 分钟项目讲解脚本

1. 业务问题：售后客服常见问题既有通用政策咨询，也有订单级判断和安全边界。
2. 系统架构：FastAPI 接收请求，LangGraph 编排 Tool，底层是 RAG、SQLite 和规则引擎。
3. 工具边界：订单查询、退款规则、政策问答和工单写入各自独立。
4. RAG 检索实验：比较 BM25、Dense、Hybrid，当前 Policy QA 默认 BM25 Top3。
5. 真实 badcase：保修 manual_review、已发货取消引用偏差、Dense/Hybrid 排序偏差。
6. LangGraph 路由：规则基线分类，缺订单号、工单确认、人工处理都有受控分支。
7. FastAPI 与可观测性：request_id、结构化日志、工具耗时、API 错误结构。
8. 评测与稳定性：pytest、真实 Policy QA 验收、Agent 离线评测、API 验收、稳定性测试、full checks。
9. 项目边界：个人项目、模拟数据、非生产级，不代表真实平台或线上部署。
