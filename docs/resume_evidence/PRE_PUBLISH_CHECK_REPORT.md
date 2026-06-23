# GitHub 发布前检查报告

- 检查时间：2026-06-23T13:36:47
- 是否通过高风险检查：True
- 是否存在 .env：True
- 是否存在 orders.db：True
- 是否存在 policy_faiss.index：True
- 本地安全忽略项数量：17
- 已跟踪风险项数量：0
- 缺失忽略规则项数量：0

## local_only_safe

- `.env`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。
- `logs/agent_api.log`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。
- `data/orders.db`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。
- `data/indexes`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。
- `eval_results`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。
- `.pytest_cache`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。
- `app/__pycache__`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。
- `app/agent/__pycache__`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。
- `app/api/__pycache__`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。
- `app/llm/__pycache__`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。
- `app/observability/__pycache__`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。
- `app/retrieval/__pycache__`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。
- `app/schemas/__pycache__`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。
- `app/services/__pycache__`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。
- `app/tools/__pycache__`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。
- `scripts/__pycache__`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。
- `tests/__pycache__`：可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。

## tracked_risk

- 无。

## ignore_rule_missing

- 无。

## 失败风险项

- 未发现会阻断发布的风险项。

## .gitignore 覆盖情况

- `!.env.example`：True
- `*.pyc`：True
- `.env`：True
- `.env.*`：True
- `.pytest_cache/`：True
- `.venv/`：True
- `__pycache__/`：True
- `data/indexes/`：True
- `data/orders.db`：True
- `eval_results/`：True
- `logs/*.log`：True
- `venv/`：True

## 说明

- 本脚本不会读取或打印 `.env` 内容。
- 疑似密钥检查只报告文件路径和规则，不输出命中的敏感文本。
- 发现风险不代表一定不能发布，但需要人工确认处理策略。
