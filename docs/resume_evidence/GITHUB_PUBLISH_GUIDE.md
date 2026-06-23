# GitHub 发布准备指南

本指南只覆盖本地发布准备，不执行 git commit、push、GitHub 登录或仓库创建。

## 发布前检查

```powershell
python scripts\pre_publish_check.py
```

重点查看：

- `.env` 是否存在且未被提交。
- 是否存在疑似 API Key。
- `logs/*.log` 是否需要清理。
- `__pycache__` 和 `.pytest_cache` 是否清理。
- `data/orders.db` 和 `data/indexes/policy_faiss.index` 是否决定提交，或改为由脚本生成。
- `.gitignore` 是否覆盖关键敏感文件。

## 推荐发布流程

1. 运行测试和全量回归：

```powershell
python -m pytest -q
python scripts\run_full_checks.py
```

2. 生成发布前报告：

```powershell
python scripts\pre_publish_check.py
```

3. 人工确认 `.env`、日志、缓存、数据库和索引文件是否进入提交范围。

4. 准备 GitHub 仓库描述：

```text
docs/GITHUB_REPOSITORY_DESCRIPTION.md
```

5. 提交前再次检查：

```powershell
git status --short
```

## 不应发布的内容

- 真实 `.env`。
- API Key、账号、密码。
- 真实用户、真实订单、真实客服记录。
- 未脱敏日志。
- 声称已完成但未验证的 Docker、线上 Demo 或生产部署能力。

## 建议发布边界说明

README 和仓库描述中应明确：

- 本项目使用模拟电商政策、订单和工单数据。
- 当前 Docker 验证状态如果未完成，应写“未验证”。
- 当前评测指标来自受控评测集，不代表真实线上泛化效果。
