# 项目证据索引

本索引用于快速定位 README、简历和面试讲解中每个说法的证据来源。

| 证据文件 | 可证明内容 | 可用于简历 | 边界 |
|---|---|---|---|
| `data/indexes/policy_index_manifest.json` | 政策文档数量、chunk 数量、索引生成信息 | 是 | 模拟政策库 |
| `eval_results/policy_retrieval_comparison.json` | BM25 / Dense / Hybrid 检索对比 | 是 | 18 条政策检索评测题 |
| `eval_results/policy_qa_live_acceptance.json` | 固定真实 DeepSeek 政策问答验收 6/6 | 是 | 不代表开放域泛化 |
| `eval_results/after_sales_agent_eval_summary.json` | 71 条 Agent 离线评测，69 条端到端通过，安全门控 71/71 | 是 | 受控离线评测集 |
| `eval_results/agent_api_acceptance.json` | 本地 API 验收场景，包含 `/health` 和 `/agent/run` | 是 | 本地单进程 |
| `eval_results/stability_test_summary.json` | 顺序稳定性、基础并发、`agent_busy` 保护 | 是 | 非生产压测 |
| `eval_results/full_check_summary.json` | 初始化、索引、pytest、API 验收、稳定性全量回归 | 是 | 以当前脚本范围为准 |
| `docs/FINAL_VERIFICATION.md` | 发布前验证命令、真实结果和 CI 边界 | 是 | 文档记录 |
| `docs/BADCASE_ANALYSIS.md` | ASAE007、ASAE016 和历史 RAG badcase 复盘 | 是 | 工程复盘 |
| `docs/policy_research_notes.md` | 模拟政策调研边界和公开流程参考 | 是 | 不代表真实平台政策 |
| `README.md` | 当前能力、运行方式、指标和安全边界 | 是 | 需随项目更新 |

## 不应写入简历的说法

- 已上线或完成线上部署验证。
- 使用真实电商数据、真实订单或真实售后工单。
- 自动执行真实退款或真实订单取消。
- production-ready。
- Docker 已完成真实构建和线上验证。
- 71 条离线评测等同于开放域线上准确率。
