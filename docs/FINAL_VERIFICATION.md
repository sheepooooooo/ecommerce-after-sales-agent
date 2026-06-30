# 最终验证记录

本文记录发布前本地验证口径。所有结果均来自本地模拟数据和本地脚本，不代表线上生产环境。

## 已执行命令

```powershell
python scripts\demo_after_sales_agent.py
python scripts\evaluate_after_sales_agent.py
python -m pytest -q
python scripts\run_full_checks.py
git diff --check
git status --short
git check-ignore -v .env data\orders.db logs\agent_api.log data\indexes eval_results
```

## Agent 离线评测

当前受控离线 Agent 评测集共 79 条，端到端通过 77 条。

| 指标 | 通过数 / 适用总数 | 比率 |
|---|---:|---:|
| 总样本 | 77 / 79 | 0.9747 |
| intent_accuracy | 76 / 78 | 0.9744 |
| route_or_status_accuracy | 77 / 79 | 0.9747 |
| tool_selection_accuracy | 77 / 78 | 0.9872 |
| entity_extraction_accuracy | 78 / 78 | 1.0000 |
| safety_gate_pass_rate | 79 / 79 | 1.0000 |
| response_schema_valid_rate | 79 / 79 | 1.0000 |
| end_to_end_success_rate | 77 / 79 | 0.9747 |
| controlled_workflow | 9 / 9 | 1.0000 |
| multi_turn_resume | 8 / 8 | 1.0000 |

失败样本保留为真实 badcase：`ASAE007`、`ASAE016`。不通过删除样本或修改预期来提升指标。

## pytest 与 full checks

发布前应以实际运行结果为准。当前本地验证目标：

- `python -m pytest -q`：全部通过。
- `python scripts\run_full_checks.py`：初始化数据、构建索引、pytest、API 验收和稳定性测试均通过。

`run_full_checks.py` 会运行本地 API 验收和稳定性测试，但不代表线上部署验证。

## CI 说明

`.github/workflows/ci.yml` 在 Windows runner 上安装依赖并运行：

```powershell
python -m pytest -q
```

CI 不依赖 `.env`、不需要真实 API Key、不调用真实 DeepSeek，不代表线上 LLM 可用性或真实并发能力。

## 当前不能验证的事项

- 真实线上 LLM 的长期稳定性、速率限制和余额状态。
- 真实用户身份、权限、审计和数据隔离。
- 真实支付、退款、物流和客服系统集成。
- 分布式并发、跨进程 session、Redis 或高可用部署。
- Docker 镜像在线上环境的长期运行表现。

## 安全检查口径

以下本地产物必须被 `.gitignore` 忽略，不能提交到 GitHub：

- `.env`
- `data/orders.db`
- `data/indexes/`
- `logs/*.log`
- `eval_results/`

`.env.example`、`data/policies/`、`docs/`、`tests/`、`scripts/` 可以提交。
