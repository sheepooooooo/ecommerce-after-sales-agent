# 技术细节说明

## BM25、Dense Retrieval、Hybrid RRF

BM25 是关键词检索，适合退款、保修、发票、优惠券等明确业务词。Dense Retrieval 使用 BGE 模型把文本编码成向量，适合语义相近表达。Hybrid RRF 融合 BM25 和 Dense 的排名，而不是直接相加分数。

Hybrid 不必然更好。当前结果中 Hybrid Hit@3 为 0.9333，低于 BM25 的 1.0000，说明在小规模、术语明确的政策库中，关键词匹配仍很强。

## 为什么 Policy QA 默认 BM25 Top3

当前检索实验显示 BM25 Top3 覆盖稳定，Hit@3 为 1.0000。Policy QA 默认使用 BM25 Top3，是为了先保证证据召回可解释、稳定，并减少向量相似误召回带来的业务偏差。

## BGE、归一化与 FAISS IndexFlatIP

BGE small 中文模型用于把政策 chunk 编码成向量。向量经归一化后，内积可以近似表示余弦相似度。FAISS `IndexFlatIP` 做精确内积检索；当前 chunk 数约 42 个，不需要复杂近似索引。

## 向量相似不等于业务相关

向量检索可能把语义相近但业务阶段不同的政策排在前面。例如“已发货不想要”和“退款”语义接近，但更直接的证据可能来自取消/拒收政策。系统因此保留 `has_relevant_policy` 判断和 badcase 分析。

## has_relevant_policy 阈值

阈值用于避免天气、写诗等无关问题强行命中政策。当前阈值是经验基线，未经过大规模独立开发集校准。

## Policy QA 链路

链路是：检索 TopK 政策 chunk，构造成证据包，调用 LLM 生成 JSON 结构化输出，再用引用校验器检查 cited_chunk_ids 是否来自本次 retrieved_chunks。无相关政策时不调用 LLM。

## 引用校验能做什么

引用校验能证明模型引用的 chunk_id 来自本次证据包，防止引用不存在或未检索到的材料。它不能证明答案语义完全正确，也不能替代人工质量审核。

## SQLite、规则引擎与 LLM 边界

SQLite 保存模拟订单和工单。退款规则引擎基于订单事实确定性判断退款资格。LLM 只用于政策解释，不负责订单事实判断、退款结论或自动写库。

## LangGraph 概念落地

State 保存单次请求信息。Node 执行单一职责，例如实体提取、意图分类、Tool 调用或格式化。Conditional Edge 根据意图、订单号和确认标志路由到不同节点。

## request_id、工具耗时与结构化日志

API 中间件生成或透传 request_id，并写入响应 Header。真实 Tool 调用会记录 `latency_ms`。API 日志以 JSON Lines 写入，记录 endpoint、intent、tool_used、answer_status、latency 和脱敏订单号。

## 并发保护

FastAPI 使用进程内 `asyncio.Semaphore` 做基础保护，达到上限返回 `503 agent_busy`。这是本地单进程保护，不是分布式限流。

## bootstrap、稳定性测试和全量验收

`bootstrap_runtime.py` 检查数据库和索引。`stability_test.py` 真实启动本地服务并测试重复调用、基础并发和日志安全。`run_full_checks.py` 串联初始化、索引构建、pytest、API 验收和稳定性测试。

## Docker 配置

Dockerfile 提供容器化配置，启动时先 bootstrap 再运行 Uvicorn。当前环境没有 Docker CLI，因此未完成镜像实际构建验证。

## 当前工程边界

项目不包含多 Agent、Memory、MCP、网页搜索、LLM 意图路由、复杂前端、生产级鉴权、高可用、监控平台或真实业务接入。
