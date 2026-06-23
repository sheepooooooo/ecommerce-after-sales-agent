# 项目结构

```text
ecommerce_after_sales_agent/
├─ app/
│  ├─ agent/
│  ├─ api/
│  ├─ llm/
│  ├─ observability/
│  ├─ retrieval/
│  ├─ schemas/
│  ├─ services/
│  ├─ tools/
│  ├─ api_server.py
│  └─ config.py
├─ data/
│  ├─ policies/
│  ├─ indexes/
│  └─ orders.db
├─ docs/
├─ eval/
├─ eval_results/
├─ logs/
├─ scripts/
├─ tests/
├─ Dockerfile
├─ README.md
└─ requirements.txt
```

## app/agent/

LangGraph 单 Agent 编排层。负责订单号提取、规则意图分类、条件路由、节点实现和统一响应格式化。

## app/api/

FastAPI 请求/响应 schema、依赖注入和异常处理。测试可通过 dependency override 注入 Policy QA stub，避免真实调用 LLM。

## app/retrieval/

政策文档加载、切块、BM25、FAISS 向量检索和 Hybrid RRF。它只负责检索候选证据，不直接生成最终回答。

## app/services/

承载业务服务逻辑，包括退款规则引擎、Policy QA 服务和引用校验。退款规则不读数据库，便于独立测试。

## app/tools/

Agent 可调用的业务工具，包括订单查询、模拟工单创建、退款资格判断和政策问答 Tool。Graph 只调用这些 Tool，不复制 SQL、规则或 RAG 逻辑。

## app/observability/

结构化日志、订单号脱敏、工具耗时统计和日志字段压缩。目标是可追踪，而不是生产级监控平台。

## data/

保存模拟政策、索引文件和 SQLite 模拟订单库。数据均为学习项目构造，不代表真实电商平台。

## scripts/

初始化、索引构建、演示、评测、API 验收、稳定性测试和全量回归入口。脚本中的 print 仅用于本地学习演示。

## tests/

pytest 测试，覆盖检索、Policy QA、规则引擎、Tool、LangGraph Agent、FastAPI、bootstrap 和稳定性 helper。

## eval/

离线评测问题集。评测集与政策库分离，避免把测试答案直接写入知识库。

## eval_results/

保存检索实验、Policy QA、Agent、API、稳定性和全量验收结果。项目总结中的指标均来自这里的真实文件。

## docs/

设计说明、验收说明、badcase 分析、部署稳定性说明和面试材料。
