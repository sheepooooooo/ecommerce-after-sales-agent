# 简历数据补齐清单

## A. 当前电商 Agent 已可直接使用的真实指标

- 政策文档数量：见 `data/indexes/policy_index_manifest.json`。
- 政策 chunk 数量：见 `data/indexes/policy_index_manifest.json`。
- BM25 / Dense / Hybrid Hit@1、Hit@3：见 `eval_results/policy_retrieval_comparison.json`。
- Policy QA 真实模型验收通过数：见 `eval_results/policy_qa_live_acceptance.json`。
- Agent 受控评测题数、意图识别、工具选择、订单号提取、缺参处理、工单确认安全门控：见 `eval_results/after_sales_agent_eval_summary.json`。
- API 验收场景：见 `eval_results/agent_api_acceptance.json`。
- 顺序稳定性和基础并发检查：见 `eval_results/stability_test_summary.json`。
- 全量回归状态：见 `eval_results/full_check_summary.json`。

## B. 科研文献 RAG 仍待补齐的指标

- 是否存在人工标注评测集。
- Hit@K。
- Recall@K。
- MRR。
- 检索延迟和生成延迟。
- 检索结果 badcase 分析。
- rerank 前后对比。
- 不同 chunk 策略对比。

当前仓库不是科研文献 RAG 项目，不能直接声称科研文献 RAG 的 Recall@K 或 MRR。

## C. 每项如何获取

- Hit@K：需要每个问题有至少一个人工标注正确来源，检查 TopK 检索结果是否命中任一正确来源。
- Recall@K：需要每个问题标注完整相关来源集合，计算 TopK 找回的相关来源数量 / 全部相关来源数量。
- MRR：需要每个问题标注至少一个正确来源，记录第一个正确命中的排名，计算 `1 / rank` 后求平均。
- 延迟：需要评测脚本记录每题检索耗时、生成耗时、总耗时。
- badcase：需要保存逐题结果，包括 query、expected source、retrieved sources、answer、failure_reason。

## D. 如果存在人工标注，如何计算 Hit@K、Recall@K、MRR

假设每题包含：

```json
{
  "query": "...",
  "gold_sources": ["paper_a.pdf#page=3", "paper_b.pdf#page=7"],
  "retrieved_sources": ["paper_c.pdf#page=2", "paper_a.pdf#page=3"]
}
```

计算方式：

- `Hit@K = 1`：TopK 中至少一个 retrieved source 命中 gold_sources；否则为 0。
- `Recall@K = TopK 命中的 gold source 数 / gold source 总数`。
- `MRR = 1 / 第一个命中结果的排名`；如果未命中则为 0。

## E. 没有人工标注时为什么不能声称 Recall@K/MRR

Recall@K 和 MRR 都依赖“什么结果算正确”的人工标注。如果没有 gold source、gold page 或 gold chunk，就无法判断检索结果是否真正相关。

只看模型回答是否流畅，不能推出检索召回率；只看检索结果相似度，也不能推出 Recall@K。没有人工标注时，简历中只能写“已搭建评测脚本/待补齐人工标注”，不能写具体 Recall@K 或 MRR 数字。

## 当前行动项

- 使用 `scripts/check_rag_metrics_readiness.py` 检查外部 RAG 项目目录。
- 如果报告显示缺少人工标注，先补评测集标注，再计算指标。
- 如果已有标注和结果，确认脚本口径后再把指标写入简历。
