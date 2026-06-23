# 基于 LangGraph 的电商售后客服 Agent

## 项目简介

本项目是“基于 LangGraph 的电商售后客服 Agent（个人项目）”。它是一个面试展示级、工程化单 Agent 业务系统，使用模拟电商政策、模拟订单和模拟工单数据，演示 RAG、Tool Calling、规则引擎、FastAPI 服务化、结构化日志、稳定性测试和 Docker 配置。

本项目不是生产级高可用系统，不代表真实电商平台，不执行真实退款、真实取消订单或真实售后动作。

简历证据与指标：`docs/resume_evidence/AGENT_METRICS.md`

GitHub 发布前检查：`docs/resume_evidence/PRE_PUBLISH_CHECK_REPORT.md`

## 主要能力

1. 政策咨询：基于模拟政策知识库的 RAG / Policy QA。
2. 订单查询：通过 SQLite 查询模拟订单事实。
3. 退款资格判断：由确定性规则引擎基于订单事实输出。
4. 模拟工单创建：必须显式确认后才写入本地模拟工单。
5. 高风险问题人工处理建议：账户安全、重复扣款、隐私投诉等不调用 LLM、不写数据库。
6. FastAPI 服务化：提供 `/health` 和 `/agent/run`。
7. 可观测性与验收：request_id、tool_trace、工具耗时、结构化日志、API 验收、稳定性测试和全量回归脚本。

## 快速启动

```powershell
python scripts\init_demo_data.py
python scripts\build_all_policy_indexes.py
python -m uvicorn app.api_server:app --host 127.0.0.1 --port 8011 --reload
```

Swagger 地址：

```text
http://127.0.0.1:8011/docs
```

新开终端运行 Demo 请求：

```powershell
python scripts\demo_api_requests.py
```

自动化验证：

```powershell
python scripts\run_full_checks.py
```

不要把 API Key 写入 README、Dockerfile、测试或日志。需要真实 Policy QA 时，请使用本地 `.env` 或运行环境变量传入。

## 项目文档导航

- [项目总结](docs/PROJECT_SUMMARY.md)：项目背景、能力、技术栈、真实结果和边界。
- [项目架构](docs/PROJECT_ARCHITECTURE.md)：总体架构和 LangGraph 工作流。
- [项目结构](docs/PROJECT_STRUCTURE.md)：目录职责说明。
- [技术细节](docs/TECHNICAL_DETAILS.md)：RAG、LangGraph、日志、稳定性和 Docker 配置细节。
- [代码阅读导航](docs/代码阅读导航.md)：用于学习项目代码的中文阅读顺序、文件职责表和核心调用链，不属于运行时功能。
- [Demo 指南](docs/DEMO_GUIDE.md)：3 分钟演示和 7 分钟讲解脚本。
- [简历描述](docs/RESUME_BULLETS.md)：精简版和工程细节版 bullet。
- [面试问答](docs/INTERVIEW_QA.md)：项目高频问答。
- [Badcase 分析](docs/BADCASE_ANALYSIS.md)：真实问题、根因和修复方式。
- [最终检查清单](docs/FINAL_PROJECT_CHECKLIST.md)：完成度和边界。
- [部署与稳定性](docs/deployment_and_stability.md)：bootstrap、稳定性测试、Docker 和全量验收。

## 快速演示路径

1. 打开 Swagger，调用 `/health`。
2. 调用 `/agent/run` 查询 `ORD10003 现在是什么状态？`。
3. 调用 `/agent/run` 判断 `ORD10004 可以退款吗？`。
4. 调用 `/agent/run` 输入 `我想退款`，观察缺订单号追问。
5. 调用 `/agent/run` 创建工单但不确认，观察 `ticket_confirmation_required`。
6. 再次调用并传 `confirm_ticket_creation=true`，观察模拟工单创建。
7. 输入 `我的银行卡被重复扣款了`，观察人工处理建议。
8. 输入 `耳机保修多久？`，观察 Policy QA 回答和引用。

## 已知边界

- Agent 评测指标来自受控评测集，不代表真实开放场景泛化能力。
- 当前使用规则路由基线，不是 LLM 意图路由。
- Dockerfile 已生成，但当前环境未检测到 Docker CLI，因此未完成镜像实际构建验证。
- 当前 API 是本地单进程模拟服务，不包含生产级鉴权、限流、高可用或监控平台。
- 当前不包含多 Agent、Memory、MCP、网页搜索或复杂前端。

## 项目目标

本项目用于学习 AI Agent 在电商售后场景中的基础实现方式。当前已实现模拟订单数据、基础订单 Tool、退款资格规则引擎、政策检索、可溯源政策问答 RAG 基线，以及基于 LangGraph 的受控多工具售后 Agent 工作流。

当前仍不实现前端、多 Agent、Memory、MCP 或网页搜索；Dockerfile 已配置但未在当前环境完成实际镜像构建验证。

## 当前目录结构

```text
ecommerce_after_sales_agent/
├─ app/
│  ├─ config.py
│  ├─ __init__.py
│  ├─ retrieval/
│  │  ├─ __init__.py
│  │  ├─ policy_schema.py
│  │  ├─ policy_loader.py
│  │  ├─ policy_index_manager.py
│  │  ├─ bm25_retriever.py
│  │  └─ policy_retriever.py
│  ├─ services/
│  │  ├─ __init__.py
│  │  └─ refund_rule_engine.py
│  └─ tools/
│     ├─ __init__.py
│     ├─ order_tool.py
│     ├─ refund_eligibility_tool.py
│     └─ policy_retrieval_tool.py
├─ data/
│  ├─ policies/
│  │  ├─ cancellation_policy.md
│  │  ├─ refund_return_policy.md
│  │  ├─ shipping_policy.md
│  │  ├─ invoice_warranty_policy.md
│  │  ├─ exchange_policy.md
│  │  ├─ coupon_policy.md
│  │  ├─ payment_policy.md
│  │  ├─ membership_points_policy.md
│  │  ├─ complaint_privacy_policy.md
│  │  └─ service_scope_policy.md
│  ├─ indexes/
│  │  ├─ policy_chunks.jsonl
│  │  └─ policy_index_manifest.json
│  └─ orders.db
├─ docs/
│  └─ policy_research_notes.md
├─ eval/
│  └─ policy_retrieval_eval_questions.jsonl
├─ eval_results/
│  ├─ policy_retrieval_results.jsonl
│  ├─ policy_retrieval_summary.json
│  └─ policy_retrieval_report.md
├─ scripts/
│  ├─ init_demo_data.py
│  ├─ build_policy_index.py
│  ├─ demo_policy_retrieval.py
│  └─ evaluate_policy_retrieval.py
├─ tests/
│  ├─ test_order_tool.py
│  ├─ test_refund_rule_engine.py
│  ├─ test_refund_eligibility_tool.py
│  ├─ test_policy_loader.py
│  ├─ test_policy_retriever.py
│  └─ test_policy_retrieval_tool.py
├─ README.md
└─ requirements.txt
```

## 当前已实现功能

1. 创建智选商城的 4 份模拟售后政策文档。
2. 使用 SQLite 创建本地模拟订单数据库 `data/orders.db`。
3. 写入 `ORD10001` 到 `ORD10012` 共 12 条固定模拟订单。
4. 提供订单查询 Tool：按订单号查询订单。
5. 提供工单 Tool：创建模拟售后工单、按订单号或全部列出工单。
6. 提供退款资格规则引擎：根据订单事实确定性判断是否可退款。
7. 提供退款资格 Tool：查询订单后调用规则引擎，返回统一结构化结果。
8. 构建 10 份模拟政策文档，并记录公开政策流程调研结论。
9. 提供 BM25 政策检索基线，支持政策 chunk 构建、检索演示和离线评测。
10. 提供 pytest 测试，验证订单查询、工单创建、退款规则、退款 Tool 和政策检索能力。

## 第二阶段：退款资格规则引擎

### 为什么退款判断不交给 LLM

退款资格判断依赖订单状态、签收时间、是否拆封、是否存在质量问题等确定性业务事实。此类判断需要稳定、可复现、可测试，不适合交给 LLM 自由生成结论。

后续 LangGraph Agent 可以决定“什么时候调用退款资格 Tool”，但是否符合退款条件，应由明确规则引擎判断。

### 为什么采用“订单查询 + 规则引擎”

本项目将订单事实查询和退款资格判断拆开：

1. `app/tools/order_tool.py` 负责从 SQLite 查询订单事实。
2. `app/services/refund_rule_engine.py` 负责纯业务规则判断，不读取数据库。
3. `app/tools/refund_eligibility_tool.py` 负责把订单查询结果交给规则引擎。

这样设计便于独立测试规则，也方便后续接入 LangGraph、FastAPI 或评测模块。

### 当前支持的退款判断场景

1. 未付款订单：不适用退款。
2. 已取消订单：不适用重复退款。
3. 已退款订单：不可重复退款。
4. 已付款但未发货：可取消订单并退款。
5. 已发货但未签收：不可直接退款，可拒收或签收后按退货政策处理。
6. 已签收且有质量问题：15 天内可退货退款或换货，超过 15 天转人工或保修。
7. 已签收、无质量问题、未拆封：7 天内可退货退款，超过 7 天不可退。
8. 已签收、无质量问题、已拆封：不支持非质量问题退货。
9. 字段缺失、状态未知或时间异常：返回 `manual_review`。

### 运行退款 Tool

```powershell
python app\tools\refund_eligibility_tool.py
```

### 第二阶段已知边界

1. 当前政策规则是模拟的，不代表真实电商平台规则。
2. 当前不会真正退款，也不会真实取消订单。
3. 超出规则范围的问题返回 `manual_review`，建议转人工处理。
4. 当前 `policy_references` 只是规则来源信息，不是 RAG 检索结果。

## 工程化约束

1. `app/tools/` 只存放可被后续 Agent 调用的业务工具函数。
2. `data/` 只存放模拟数据、政策文档和 SQLite 数据库。
3. `scripts/` 只存放初始化或运维脚本。
4. `tests/` 只存放自动化测试。
5. 业务政策保存在 Markdown 文档中，不硬编码进 Python 逻辑。
6. 所有 SQL 查询和写入都使用参数化语句。
7. 当前阶段不写入任何 API Key、账号、密码或真实用户数据。
8. 当前 Tool 只创建模拟工单，不执行真实退款、真实订单取消等不可逆操作。

## 模拟数据声明

本项目使用模拟电商政策、模拟订单和模拟工单数据，仅用于学习 LangGraph Agent、RAG、Tool Calling 和业务工作流开发，不代表任何真实电商平台或真实售后政策。

商城名称统一为：智选商城。

## 初始化数据库

```powershell
python scripts\init_demo_data.py
```

## 运行测试

```powershell
python -m pytest -q
```

## 手动运行 Tool

```powershell
python app\tools\order_tool.py
```

## 手动运行退款资格 Tool

```powershell
python app\tools\refund_eligibility_tool.py
```

## 第三阶段 A：政策知识库构建与 BM25 检索基线

### 阶段定位

当前阶段先独立完成 RAG 中的 R，也就是 Retrieval 检索层。系统会把 `data/policies/*.md` 中的模拟政策文档切分成 chunk，构建本地 JSONL 索引，再使用 BM25 做关键词检索。

当前阶段不调用 LLM，不生成最终自然语言政策答案，也不使用 OpenAI API、Embedding、FAISS、LangGraph 或 FastAPI。

### Markdown 如何变成检索 chunk

政策加载器会读取 `data/policies/*.md`，优先使用一级标题作为文档标题，再按二级标题 `## ` 切分。一个二级标题及其正文组成一个 chunk，并保存来源文件、文档标题、小节标题和正文内容。

按标题切块比固定字符数切块更适合政策文档，因为“适用范围”“标准流程”“例外与人工处理情形”“Agent 可执行边界”本身就是业务语义单元。固定字符数可能把一条完整规则切断，降低检索结果的可解释性。

### 为什么构建索引和检索服务分离

构建索引用于离线读取 Markdown、生成 `policy_chunks.jsonl` 和 `policy_index_manifest.json`。检索服务只读取已经构建好的索引并执行 BM25 检索。

这样做可以让政策变化、索引版本和在线检索行为分开排查。manifest 中保存来源文件和 sha256，后续可以用于判断政策文档变化后是否需要重建索引。

### BM25 的优势和局限

BM25 对“订单取消、退款、保修、发票、优惠券、支付异常”等业务术语有较好的关键词匹配能力，检索结果也容易解释。

它的局限是不能真正理解语义和同义表达，例如用户没有使用政策中的关键词时，召回可能变差。后续阶段将新增 Embedding + FAISS，并与 BM25 做混合检索和效果对比。

### 评测集和政策库为什么分离

评测问题保存在 `eval/policy_retrieval_eval_questions.jsonl`，政策文档保存在 `data/policies/`。两者分离可以避免把测试答案直接写进知识库，也方便后续比较 BM25、向量检索和混合检索的真实差异。

评测问题尽量接近真实用户口语，不直接复制政策标题或政策原句。

### 运行政策检索流程

```powershell
python -m pip install -r requirements.txt
python scripts\build_policy_index.py
python scripts\demo_policy_retrieval.py
python scripts\evaluate_policy_retrieval.py
python -m pytest -q
```

### 第三阶段 A 已知边界

1. 目前仅完成政策检索，不生成最终自然语言政策答案。
2. 目前未使用向量检索、Embedding、FAISS 或 LLM。
3. 当前政策均为模拟政策，参考公开常见电商售后流程后重新设计。
4. 无关问题不强行命中政策，而是返回无相关政策。
5. 后续将加入 Embedding、FAISS、混合检索和政策问答生成。

## 第三阶段 B：语义检索与混合检索实验

### BM25、Dense、Hybrid 的区别

BM25 是关键词检索，适合“退款”“取消”“保修”“优惠券”等明确业务词。它可解释性强，但对同义表达和口语化表达不够敏感。

Dense Retrieval 使用 `BAAI/bge-small-zh-v1.5` 将文本编码为向量，再用 FAISS 搜索相似向量。它更适合语义相近表达，但向量相似不等于业务正确。

Hybrid Retrieval 使用 RRF 将 BM25 和 Dense 的排名融合。RRF 只融合排名，不直接相加原始分数，因为 BM25 分数和 dense score 的量纲不同。

### FAISS 与相关性判断

FAISS 只负责向量近邻搜索。即使用户问天气、股票或写诗，FAISS 也可能返回最相近的政策 chunk。因此系统增加了 `has_relevant_policy` 和相关性阈值判断，避免把无关问题强行回答成售后政策。

当前 Dense 相关性阈值来自 `DEFAULT_DENSE_RELEVANCE_THRESHOLD`，它是经验基线，尚未通过独立开发集严格校准。

### 为什么选择 IndexFlatIP

当前知识库只有约 40 个 chunk，使用精确搜索的 `IndexFlatIP` 更简单、稳定、可解释。现阶段不提前实现 IVF、HNSW、Milvus 等复杂索引。

### 运行语义检索与对比实验

```powershell
python -m pip install -r requirements.txt
python scripts\build_all_policy_indexes.py
python scripts\demo_policy_retrieval.py
python scripts\evaluate_policy_retrieval.py
python -m pytest -q
```

### 第三阶段 B 已知边界

1. 当前仅完成政策检索，不生成最终自然语言回答。
2. 当前阈值为经验基线，尚未通过独立开发集严格校准。
3. 当前向量模型首次加载依赖网络和本地缓存。
4. 当前知识库只有约 40 个 chunk，不代表大规模向量库性能。
5. 后续会接入 LLM 生成、订单 Tool 和 LangGraph 工作流。

## 第三阶段 C：可溯源政策问答 RAG 服务

### 阶段定位

当前阶段在政策检索能力之上，新增受证据约束的政策问答服务。服务默认使用 `bm25` 检索模式和 `top_k=3`，因为当前检索实验显示，在小规模且政策术语明确的知识库中，BM25 Top3 覆盖最好。

API 和 Service 仍保留 `bm25`、`dense`、`hybrid` 三种可选模式。后续应在更大、更口语化的独立评测集上继续校准默认策略。

### 为什么检索到内容不等于可以自由回答

检索结果只是候选证据。模型只能根据本次 TopK 政策 chunk 回答，不能使用未检索到的政策、常识或真实平台规则自由补全。无相关政策时，系统不会调用 LLM，而是返回 `no_relevant_policy`。

### 为什么引用必须校验

模型输出必须列出引用的 `chunk_id`。引用校验器会确定性检查这些 `chunk_id` 是否来自本次 retrieved_chunks，防止模型引用不存在或本次未检索到的政策片段。

引用校验只检查“引用是否属于本次证据”，不保证全部语义结论绝对正确，也不能替代人工质量审核。

### 政策问答不能替代订单查询和退款规则判断

政策问答只处理政策咨询，例如保修、发票、优惠券、支付异常、已发货拒收等一般规则。具体订单问题，例如 `ORD10004 可以退款吗？`，需要订单查询 Tool 和退款资格规则引擎，不能只靠政策问答直接确认。

### 配置 .env

复制示例文件：

```powershell
copy .env.example .env
```

然后在 `.env` 中填写自己的 `DEEPSEEK_API_KEY`。不要把真实 API Key 写入代码、README、测试或日志。

可选配置：

```env
LLM_ENABLE_THINKING=false
```

默认关闭 thinking，用于降低政策问答 JSON 输出的延迟和格式不稳定风险。

### 运行政策问答流程

```powershell
python -m pip install -r requirements.txt
python scripts\build_all_policy_indexes.py
python scripts\check_llm_connection.py
python scripts\demo_policy_qa.py
python scripts\evaluate_policy_qa.py
python -m pytest -q
```

### 真实模型验收

mock 单元测试只能验证本地逻辑，不能验证真实 DeepSeek 服务、JSON Object 输出模式、模型延迟和引用字段稳定性。完成 `.env` 配置后，可手动运行：

```powershell
python scripts\check_llm_connection.py
python scripts\run_policy_qa_live_acceptance.py
python scripts\evaluate_policy_qa.py
python -m pytest -q
```

`run_policy_qa_live_acceptance.py` 会真实调用 DeepSeek，并生成：

```text
eval_results/policy_qa_live_acceptance.json
eval_results/policy_qa_live_acceptance_report.md
```

该验收脚本不纳入 pytest，不写入 API Key，不保存完整系统 Prompt 或完整 API 原始响应，也不执行真实退款、取消订单或工单创建。详细说明见 `docs/policy_qa_live_acceptance.md`。

### 第三阶段 C 已知边界

1. 当前所有政策均为模拟政策。
2. 当前问答只能基于检索到的政策 chunk。
3. 引用校验只检查引用是否属于本次证据，不保证全部语义结论绝对正确。
4. 当前不会查询订单、判断某笔订单退款资格或执行任何真实售后动作。
5. 后续会由 LangGraph 根据意图路由到政策问答、订单查询、退款规则和工单 Tool。

以上手动运行命令中的打印输出仅用于本地学习演示，不作为正式日志方案。后续阶段可扩展 request_id、结构化日志和工具调用轨迹。

## 第四阶段 A：LangGraph 多工具售后 Agent

### 阶段定位

当前阶段新增一个单 Agent、受控 LangGraph 图工作流，用来编排已有 Tool：

1. `policy_qa_tool.ask_policy_question`：政策问答，可调用 LLM。
2. `order_tool.get_order`：订单事实查询，不调用 LLM。
3. `refund_eligibility_tool.check_refund_eligibility`：退款资格判断，不调用 LLM。
4. `order_tool.create_ticket`：创建本地模拟售后工单，必须显式确认。

当前意图路由是规则基线，只面向本项目的模拟售后场景。它不是多 Agent，也不是任意自主执行 Agent。

### 安全和边界

订单查询和退款结论由结构化订单数据与规则引擎输出，不由模型猜测。政策回答可以调用 LLM，但需要复用政策问答 Tool 的引用和 grounding verification。创建工单会写入本地模拟数据库，因此必须传入 `confirm_ticket_creation=True` 才会执行。

缺少订单号时，`order_lookup` 和 `refund_eligibility` 会返回 `missing_order_id`，不会调用订单或退款 Tool。账户安全、重复扣款、隐私投诉等高风险问题会进入人工处理建议，不调用 LLM、不写数据库。

### 运行 Agent Demo

```powershell
python scripts\init_demo_data.py
python scripts\demo_after_sales_agent.py
```

Demo 中的 print 仅用于本地学习演示，不是正式日志。如果 `.env` 未配置，政策问答场景可能提示缺少 Key，但不会影响其他订单、退款、工单和人工处理场景。

### 运行离线评测

```powershell
python scripts\evaluate_after_sales_agent.py
```

评测默认对政策问答使用 stub，不真实调用 DeepSeek。输出文件包括：

```text
eval_results/after_sales_agent_eval_results.jsonl
eval_results/after_sales_agent_eval_summary.json
eval_results/after_sales_agent_eval_report.md
eval_results/after_sales_agent_badcases.md
```

LLM 意图路由、多 Agent、Memory、MCP、前端和生产级部署将在后续阶段再考虑。

## 第四阶段 B：FastAPI 服务化与可观测性

### 阶段定位

当前阶段把已有 LangGraph 单 Agent 封装为本地 FastAPI HTTP 服务，并补充 request_id、结构化日志、基础并发保护、API 自动化测试和一键 HTTP 验收。

当前是本地单进程、模拟业务服务，不是生产级高可用系统。并发保护只使用进程内 `asyncio.Semaphore`，不是分布式限流。真实 LLM 调用仅在政策问答路径中发生；订单查询、退款判断、人工处理和工单确认等路径不依赖 LLM。

日志中不记录 API Key、密码、验证码、银行卡完整号码或完整 Prompt。当前创建的是模拟工单，不执行真实退款或真实售后动作。

### 运行 API 服务

```powershell
python scripts\init_demo_data.py
python scripts\build_all_policy_indexes.py

python -m uvicorn app.api_server:app --host 127.0.0.1 --port 8011 --reload
```

Swagger 地址：

```text
http://127.0.0.1:8011/docs
```

### Demo 请求

新开终端运行：

```powershell
python scripts\demo_api_requests.py
```

### 自动验收

```powershell
python scripts\run_api_checks.py
```

输出：

```text
eval_results/agent_api_acceptance.json
eval_results/agent_api_acceptance_report.md
```

### 测试

```powershell
python -m pytest -q
```

## 第五阶段：稳定性、容器化与全量回归验收

### 阶段定位

当前阶段不新增业务能力，只验证和打包已有系统：FastAPI API、LangGraph 售后 Agent、政策 RAG / Policy QA、SQLite 订单与工单 Tool、退款规则引擎、结构化日志和 API 验收脚本。

当前项目是本地单进程、模拟业务、面试展示级工程化系统。Docker 配置不等于已经完成线上生产部署；进程内 Semaphore 不是分布式限流；当前不包含数据库持久化、高可用、鉴权、监控平台或生产级安全体系。

### 全量本地验收

```powershell
python scripts\run_full_checks.py
```

### 单独稳定性测试

```powershell
python scripts\stability_test.py
```

稳定性测试会真实启动本地 Uvicorn 到 8012 端口，覆盖重复 HTTP 调用、基础并发调用、request_id 唯一性和日志敏感信息检查。它不是高并发压测，也不是生产级性能测试。

### Docker 构建与启动

```powershell
docker build -t ecommerce-after-sales-agent:local .
```

```powershell
docker run --rm -p 8011:8011 ^
  -e DEEPSEEK_API_KEY=你的Key ^
  ecommerce-after-sales-agent:local
```

不要把 Key 写进 Dockerfile，不要把 `.env` 提交 Git。默认 API 验收和稳定性测试不会调用真实 LLM。当前环境未检测到 `docker` 命令，因此 Dockerfile 已生成但尚未完成实际镜像构建验证。

## 已知边界

1. 当前没有实现前端、多 Agent、Memory、MCP 或网页搜索；Dockerfile 已配置但未在当前环境完成实际镜像构建验证。
2. 当前只模拟订单查询、退款资格判断、工单创建和政策问答，不执行真实退款、真实取消订单或真实物流操作。
3. 当前已接入 API 结构化日志和基础工具轨迹，但不是生产级分布式链路追踪。
4. 当前测试数据来自初始化脚本，每次测试前会重建干净数据库，避免依赖测试执行顺序。
5. 当前政策问答只基于检索到的模拟政策 chunk，不代表真实平台政策或法律意见。
6. 当前引用校验只证明引用来自本次证据，不保证答案语义绝对正确。

## 后续阶段计划

1. 更稳健的回归验收集与坏例分析。
2. LLM 辅助意图路由实验。
3. FastAPI 的生产级鉴权、限流和部署方案。
4. 前端或管理端体验。
