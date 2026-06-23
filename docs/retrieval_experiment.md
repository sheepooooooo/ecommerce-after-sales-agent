# 语义检索与混合检索实验说明

## 实验目的

本实验用于比较智选商城模拟政策库在三种检索策略下的表现：BM25 关键词检索、BGE Embedding + FAISS 向量检索、BM25 + Dense 的 RRF 混合检索。

当前阶段只评测检索，不生成最终自然语言回答，不调用 LLM，也不接入订单 Agent 工作流。

## 三种策略定义

BM25 检索基于关键词匹配和词频统计，适合订单取消、退款、保修、优惠券等业务术语明确的问题。

Dense Retrieval 使用 `BAAI/bge-small-zh-v1.5` 将政策 chunk 和用户 query 编码成向量，再用 FAISS `IndexFlatIP` 搜索向量相似度较高的 chunk。它更适合口语化表达和同义表达，但无关问题也可能返回最相近候选。

Hybrid Retrieval 使用 Reciprocal Rank Fusion 合并 BM25 和 Dense 的候选排名。它不直接相加 BM25 原始分数和 dense 原始分数，因为两者量纲不同。

## 评测指标定义

- Hit@1：相关问题中，Top1 来源文件是否命中预期政策。
- Hit@3：相关问题中，Top3 来源文件是否包含预期政策。
- 无关问题识别准确率：无关问题是否正确返回无相关政策。
- 平均检索耗时：模型预热后的平均检索耗时，不包含首次模型加载时间。

## 实验环境说明

当前项目按 CPU 环境优先设计。BGE 模型首次运行可能需要联网下载，并缓存在 Hugging Face 本地缓存目录。当前政策库约 40 个 chunk，因此使用简单精确的 FAISS `IndexFlatIP`。

## 真实结果摘要

真实结果由以下命令生成：

```powershell
python scripts\evaluate_policy_retrieval.py
```

最近一次本地评测结果：

| 策略 | Hit@1 | Hit@3 | 无关问题识别准确率 | 平均检索耗时 ms |
| --- | ---: | ---: | ---: | ---: |
| BM25 | 0.6667 | 1.0000 | 1.0000 | 34.2998 |
| Dense | 0.7333 | 0.8667 | 1.0000 | 9.3081 |
| Hybrid | 0.7333 | 0.9333 | 1.0000 | 24.9241 |

本次 Embedding 模型首次加载和预热耗时约 13425.1937 ms。上表平均检索耗时不包含首次模型加载时间。

运行后请查看：

- `eval_results/policy_retrieval_comparison.json`
- `eval_results/policy_retrieval_comparison_report.md`
- `eval_results/policy_retrieval_bm25_badcases.md`
- `eval_results/policy_retrieval_dense_badcases.md`
- `eval_results/policy_retrieval_hybrid_badcases.md`

## Badcase 分析

Badcase 报告会列出问题、期望来源、实际 Top1、Top3 来源、是否命中和初步失败原因。不要为了让指标变成 100% 而修改评测题或硬编码答案。

## 当前结论与边界

当前阈值是经验基线，尚未使用独立开发集严格校准。Hybrid 不保证一定优于 BM25 或 Dense，最终结论应以真实评测结果为准。
