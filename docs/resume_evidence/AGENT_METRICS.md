# Agent 项目真实指标证据

本文只整理当前仓库中可由本地命令或结果文件支撑的指标。所有指标均来自模拟数据、模拟政策和受控评测集，不代表真实电商平台线上效果。

## 可写入简历的指标

| 指标 | 当前值 | 数据来源 | 推荐写法 | 使用边界 |
|---|---:|---|---|---|
| 模拟政策文档数量 | 10 | `data/policies/` | 构建 10 份模拟电商售后政策文档 | 不代表真实平台政策覆盖 |
| 政策 chunk 数量 | 42 | `data/indexes/policy_index_manifest.json` | 将政策文档切分为 42 个可追溯 chunk | chunk 数量会随政策结构变化 |
| Policy QA 真实验收 | 6 / 6 | `eval_results/policy_qa_live_acceptance.json` | 完成 6/6 条固定真实 LLM 政策问答验收 | 固定验收集，不代表开放域泛化 |
| Agent 离线评测样本 | 79 | `eval_results/after_sales_agent_eval_summary.json` | 设计 79 条售后 Agent 离线评测样本 | 受控评测集 |
| Agent 端到端通过 | 77 / 79 | `eval_results/after_sales_agent_eval_summary.json` | Agent 离线评测端到端通过 77/79 | 保留 ASAE007、ASAE016 badcase |
| 安全门控 | 79 / 79 | `eval_results/after_sales_agent_eval_summary.json` | 安全门控检查 79/79 通过 | 覆盖当前评测定义的写库和高风险场景 |
| 受控复合工作流 | 9 / 9 | `eval_results/after_sales_agent_eval_summary.json` | `refund_then_ticket_if_ineligible` 复合流程评测 9/9 通过 | 仅一个固定复合流程 |
| 多轮任务续办 | 8 / 8 | `eval_results/after_sales_agent_eval_summary.json` | 缺订单号后的多轮任务续办评测 8/8 通过 | 仅覆盖有限售后任务 |
| pytest | 129 passed / 1 warning | `python -m pytest -q` | 本地 pytest 回归 129 passed | warning 为 StarletteDeprecationWarning |
| full checks | passed | `python scripts\run_full_checks.py` | 全量本地检查通过，覆盖初始化、索引、pytest、API 验收和稳定性测试 | 不代表线上部署验证 |

## 推荐简历表述

```text
构建本地模拟电商售后 Agent：基于 SQLite 订单事实、确定性退款规则、BM25/Dense/Hybrid 政策检索与可溯源 Policy QA，实现订单查询、退款资格判断、多轮信息补全、工单确认写安全、高风险人工兜底和一个受控复合流程。设计 79 条离线 Agent 评测样本，端到端通过 77/79，安全门控 79/79，复合流程 9/9，多轮续办 8/8；完成固定真实 LLM 政策问答验收 6/6。
```

## 不建议夸大的表述

- 不写 production-ready。
- 不写自动退款。
- 不写完成线上部署验证。
- 不写真实电商平台接入。
- 不把 79 条受控评测解释为开放域准确率。
