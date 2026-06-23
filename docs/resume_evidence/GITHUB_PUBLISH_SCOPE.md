# GitHub 发布范围说明

本说明用于发布前确认哪些内容应提交到 GitHub，哪些内容只保留在本地。项目使用模拟电商政策、模拟订单和模拟工单数据，不包含真实用户数据、真实订单或真实 API Key。

## 会提交到 GitHub

- Python 源代码。
- 模拟政策 Markdown：`data/policies/`。
- README、架构文档、评测说明、项目说明文档。
- 简历证据包文档：`docs/resume_evidence/`。
- `.env.example`。
- `Dockerfile`。
- `LICENSE`。
- `CONTRIBUTING.md`。
- 测试代码。
- 初始化、构建、检查和演示脚本。

## 不会提交到 GitHub

- `.env`。
- 本地日志：`logs/*.log`。
- SQLite 数据库：`data/orders.db`。
- FAISS 索引、chunk 索引和索引 manifest：`data/indexes/`。
- 原始评测输出：`eval_results/`。
- Python 缓存：`__pycache__/`、`.pytest_cache/`、`*.pyc`。
- 本地虚拟环境：`.venv/`、`venv/`。

## 如何重新生成本地产物

模拟订单数据库可通过以下命令重新生成：

```powershell
python scripts\init_demo_data.py
```

政策 chunk 索引和 FAISS 向量索引可通过以下命令重新生成：

```powershell
python scripts\build_all_policy_indexes.py
```

评测结果可按需通过对应脚本重新生成，例如：

```powershell
python scripts\evaluate_policy_retrieval.py
python scripts\evaluate_policy_qa.py
python scripts\run_full_checks.py
```

真实模型验收会消耗 API 额度，发布前不应自动运行：

```powershell
python scripts\run_policy_qa_live_acceptance.py
```

## 发布前确认

- `.env` 可以存在于本地，但必须被 `.gitignore` 忽略且不能被 Git 跟踪。
- `logs/`、`data/orders.db`、`data/indexes/`、`eval_results/` 可以存在于本地，但必须被 `.gitignore` 忽略且不能被 Git 跟踪。
- 如果将来决定提交某些评测摘要，应优先提交整理后的 `docs/resume_evidence/`，而不是原始 `eval_results/`。
