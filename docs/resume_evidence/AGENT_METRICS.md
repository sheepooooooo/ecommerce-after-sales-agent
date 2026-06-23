# Agent 项目真实指标证据

本文档只整理当前仓库中已有结果文件和本地命令输出能够支持的指标。无法验证的数据标记为 `null`、`未找到` 或 `未验证`，不用于简历夸大描述。

## 可写入简历的指标

| 指标 | 数值 | 数据来源 | 推荐写法 | 使用边界 |
| --- | --- | --- | --- | --- |
| 政策文档数量 | 10 | `data/indexes/policy_index_manifest.json` | 构建 10 份模拟电商售后政策文档知识库 | 模拟政策，不代表真实平台政策 |
| 政策 chunk 数量 | 42 | `data/indexes/policy_index_manifest.json` | 将政策文档切分为 42 个可追溯政策 chunk | chunk 数量会随政策结构变化 |
| BM25 Hit@1 / Hit@3 | 0.667 / 1.0 | `eval_results/policy_retrieval_comparison.json` | 在 18 条政策检索评测题上，BM25 Hit@1 为 0.667、Hit@3 为 1.0 | 仅代表当前模拟评测集 |
| Dense Hit@1 / Hit@3 | 0.733 / 0.867 | `eval_results/policy_retrieval_comparison.json` | 对比 Dense FAISS 检索，Hit@1 为 0.733、Hit@3 为 0.867 | 使用 `BAAI/bge-small-zh-v1.5` |
| Hybrid Hit@1 / Hit@3 | 0.733 / 0.933 | `eval_results/policy_retrieval_comparison.json` | 实现 BM25、Dense、Hybrid 检索对比，Hybrid Hit@3 为 0.933 | 当前 RRF 融合策略与评测题口径 |
| Policy QA 真实验收 | 6 / 6 | `eval_results/policy_qa_live_acceptance.json` | 完成 6/6 条真实 LLM 政策问答验收，覆盖 JSON 输出、引用校验、订单边界和无关问题拦截 | 固定验收用例，不代表开放域泛化 |
| Agent 受控评测题数 | 24 | `eval_results/after_sales_agent_eval_summary.json` | 设计 24 条受控 Agent 评测任务 | 受控评测集 |
| intent_accuracy | 1.0 | `eval_results/after_sales_agent_eval_summary.json` | 24 条受控 Agent 评测任务中，意图识别准确率为 1.0 | 不代表真实线上准确率 |
| tool_selection_accuracy | 1.0 | `eval_results/after_sales_agent_eval_summary.json` | 工具选择准确率为 1.0 | 当前工具集和评测题 |
| order_id_extraction_accuracy | 1.0 | `eval_results/after_sales_agent_eval_summary.json` | 订单号提取准确率为 1.0 | 模拟订单号格式 |
| missing_order_id_handling_accuracy | 1.0 | `eval_results/after_sales_agent_eval_summary.json` | 缺少订单号处理准确率为 1.0 | 当前缺参场景 |
| ticket_confirmation_safety_accuracy | 1.0 | `eval_results/after_sales_agent_eval_summary.json` | 工单创建显式确认安全门控准确率为 1.0 | 创建模拟工单，不执行真实售后 |
| API 验收场景数 | 8 | `eval_results/agent_api_acceptance.json` | 完成 8 个本地 API 验收场景 | 本地单进程验收 |
| 顺序稳定性 | 12 / 12 | `eval_results/stability_test_summary.json` | 顺序稳定性测试 12/12 通过 | 本地稳定性检查 |
| 基础并发 | 5 total / 4 HTTP 200 / 1 agent_busy / 0 unexpected failure | `eval_results/stability_test_summary.json` | 基础并发测试 5 次请求中 4 次成功、1 次触发 agent_busy 保护、0 次非预期失败 | 进程内基础并发保护 |
| 未预期错误数 | 0 | `eval_results/stability_test_summary.json` | 稳定性测试未出现非预期错误 | 本地测试口径 |
| pytest passed / warning | 87 / 1 | `python -m pytest -q` 终端输出，2026-06-23 | 本地 pytest 回归 87 条用例通过，1 个 warning | warning 为 TestClient 依赖的 StarletteDeprecationWarning |
| 全量回归验收 | true | `eval_results/full_check_summary.json` | 全量回归验收通过，覆盖初始化、索引构建、pytest、API 验收和稳定性测试 | 以 `run_full_checks.py` 当前范围为准 |

## 暂不建议写入简历的指标

| 指标 | 当前值 | 数据来源 | 原因 |
| --- | --- | --- | --- |
| Docker 验证状态 | 未验证 | `docker --version` 本地命令输出 | 当前 PowerShell 环境中 `docker` 命令不可用 |

## 推荐简历表述

可组合为：

```text
构建模拟电商售后 Agent 项目：基于 SQLite 订单事实、规则引擎、BM25/Dense/Hybrid 政策检索与可溯源 Policy QA，实现订单查询、退款资格判断、工单确认安全门控和人工转接边界。设计 24 条受控 Agent 评测任务，意图识别、工具选择、订单号提取、缺参处理和工单确认安全门控指标均为 1.0；完成 6/6 条真实 LLM 政策问答验收，并在 18 条政策检索评测题上对比 BM25、Dense、Hybrid 检索效果。
```

使用边界：

- 以上指标来自模拟业务数据和受控评测集，不代表真实电商平台线上效果。
- 当前 Docker 部署验证未完成，不应写“已完成 Docker 部署验证”。
- 真实 API Key、真实用户数据、真实订单均未进入项目。
