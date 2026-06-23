# 第五阶段：部署与稳定性说明

## 系统启动流程

本地开发推荐流程：

```powershell
python scripts\bootstrap_runtime.py
python -m uvicorn app.api_server:app --host 127.0.0.1 --port 8011
```

`bootstrap_runtime.py` 会检查模拟订单数据库和政策索引。数据库缺失时创建；数据库已存在时不会重置，避免误删本地模拟工单。

## bootstrap_runtime 的职责

- 检查 `data/orders.db` 是否存在。
- 检查 `policy_chunks.jsonl`、`policy_index_manifest.json`、`policy_faiss.index`、`policy_vector_manifest.json` 是否存在。
- 索引缺失时复用现有索引构建函数。
- manifest 与当前政策文件不一致时只提示手动重建，不在服务启动阶段静默重建。

首次构建向量索引可能需要联网下载 Embedding 模型。

## 稳定性测试覆盖范围

`scripts/stability_test.py` 会真实启动 Uvicorn 到 8012 端口，覆盖：

- 顺序重复调用；
- 基础并发调用；
- 5xx 检查；
- request_id 唯一性检查；
- API 耗时统计；
- 本次追加日志 JSON 可解析与敏感信息检查。

这不是高并发压测，也不是生产级性能测试。

## 并发保护设计与边界

API 使用进程内 `asyncio.Semaphore` 做基础并发保护。超过 `MAX_CONCURRENT_AGENT_REQUESTS` 时可返回 `503 agent_busy`。该机制不是分布式限流，不适合直接宣称生产级容量保护。

## 日志和敏感信息处理

日志写入 `logs/agent_api.log`，每行一个 JSON 对象。默认记录 `query_length`，不记录完整用户问题。订单号应以 `ORD***` 脱敏形式出现。日志检查会拒绝 API Key、`.env` 内容、密码、验证码、完整银行卡号和未脱敏订单号。

## Docker 构建与运行命令

```powershell
docker build -t ecommerce-after-sales-agent:local .
docker run --rm -p 8011:8011 ^
  -e DEEPSEEK_API_KEY=你的Key ^
  ecommerce-after-sales-agent:local
```

不要把 Key 写进 Dockerfile，也不要提交 `.env`。容器默认不包含真实 API Key。若需要真实 Policy QA，应通过 Docker 环境变量传入 `DEEPSEEK_API_KEY`。

容器内 SQLite 和日志默认不具备宿主机持久化；实际运行可通过挂载 `data/` 与 `logs/` 目录解决。

## Docker 验证状态

Dockerfile 已生成，但当前环境未完成实际镜像构建验证。原因：当前 PowerShell 环境中未检测到 `docker` 命令。可在 Docker Desktop 安装并启动后执行：

```powershell
docker build -t ecommerce-after-sales-agent:local .
docker run --rm --name ecommerce-after-sales-agent-test -p 8011:8011 ecommerce-after-sales-agent:local
```

再访问：

```text
http://127.0.0.1:8011/health
```

## 全量回归验收说明

一键验收入口：

```powershell
python scripts\run_full_checks.py
```

它会依次执行初始化、构建索引、pytest、API 验收和稳定性测试。该脚本不运行真实 LLM 验收，也不代表生产级发布验证。

## 当前局限

- 当前项目是本地单进程、模拟业务、面试展示级工程化系统。
- Docker 配置不等于已经完成线上生产部署。
- 当前不包含数据库持久化、高可用、鉴权、监控平台或生产级安全体系。
