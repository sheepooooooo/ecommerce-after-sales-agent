# 项目证据索引

本索引用于快速定位简历、GitHub README、面试讲解中每个说法的证据来源。

| 证据文件 | 可证明内容 | 可用于简历 | 边界 |
| --- | --- | --- | --- |
| `data/indexes/policy_index_manifest.json` | 政策文档数量、chunk 数量、索引生成时间 | 是 | 模拟政策库 |
| `eval_results/policy_retrieval_comparison.json` | BM25 / Dense / Hybrid Hit@1、Hit@3、检索延迟 | 是 | 18 条政策检索评测题 |
| `eval_results/policy_qa_live_acceptance.json` | 真实 DeepSeek 政策问答验收 6/6 | 是 | 固定验收问题，不代表开放域 |
| `eval_results/after_sales_agent_eval_summary.json` | 24 条受控 Agent 评测与核心准确率 | 是 | 受控评测集 |
| `eval_results/agent_api_acceptance.json` | 本地 API 验收场景与 /health | 是 | 本地单进程 |
| `eval_results/stability_test_summary.json` | 顺序稳定性、基础并发、agent_busy 保护 | 是 | 非生产压测 |
| `eval_results/full_check_summary.json` | 初始化、索引、pytest、API 验收、稳定性全量回归 | 是 | 以脚本当前范围为准 |
| `docs/policy_qa_live_acceptance.md` | 为什么需要真实模型验收、验收边界 | 是 | 文档说明 |
| `docs/policy_qa_badcase_analysis.md` | Q1/Q3 badcase 根因与修复 | 是 | 工程复盘 |
| `docs/policy_research_notes.md` | 模拟政策调研边界和公开流程参考 | 是 | 不代表真实平台政策 |
| `README.md` | 项目当前能力、运行方式、已知边界 | 是 | 需随阶段更新 |
| `Dockerfile` | Docker 化运行入口存在 | 谨慎 | Docker 当前未实际验证 |

## 不应写入简历的说法

- 不应写“已上线”或“线上 Demo”，当前未验证线上部署。
- 不应写“使用真实电商数据”，项目只使用模拟订单、模拟政策和模拟工单。
- 不应写“Docker 已验证”，当前环境未识别 `docker` 命令。
- 不应写科研文献 RAG Recall@K / MRR，除非外部 RAG 项目补齐人工标注和结果文件。
