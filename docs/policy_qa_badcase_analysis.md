# 政策问答 Badcase 分析

本文档记录第三阶段 C.1 的真实 LLM 验收 badcase 修复过程。所有结论仅针对智选商城模拟政策问答项目，不代表真实平台政策、法律意见或消费者权益承诺。

## Q1：通用政策问答被过度标记为 manual_review

问题：

```text
耳机买了以后一般保修多长时间？
```

现象：

- 检索命中 `invoice_warranty_policy.md`。
- 引用校验通过。
- 模型返回 `manual_review`。
- 模型把“实际申请保修时可能需要订单号或购买凭证”误判为“当前政策解释无法回答”。

根因：

模型没有充分区分“政策解释”和“订单级执行判断”。保修期限属于通用政策解释；订单号、购买凭证、图片或检测报告是后续真实执行服务时可能需要的材料，不应让通用政策解释直接进入人工处理。

同时，live acceptance 的检索可观测性显示，BM25 Top3 虽然命中 `invoice_warranty_policy.md`，但未召回直接写明“12 个月模拟保修”的标准流程 chunk，而是优先召回适用范围、Agent 可执行边界和人工处理情形。这会让模型看到较多“需要凭证/转人工”的上下文，却没有看到最直接的保修期限证据。

修复：

- 强化系统 Prompt，明确通用政策解释问题在证据直接写明规则时应设置 `needs_human_review=false`、`missing_information=[]`。
- 明确“真实执行可能需要凭证”不等于“当前政策问答必须人工处理”。
- 在 `invoice_warranty_policy.md` 中新增“数码商品与耳机保修期限”小节，使“耳机、保修多久、保修多长时间、保修期限”等自然表达能够召回直接规则证据。
- 补充回归测试 `test_generic_policy_question_should_not_require_manual_review`，用 stub LLM 验证结构化结果仍为 `answered`。

## Q3：已发货取消问题引用了泛化退款政策

问题：

```text
商品已经发货，但我临时不想要了怎么办？
```

现象：

- 当前回答状态为 `answered`。
- 引用校验通过。
- 最终引用来源只有 `refund_return_policy.md`，未包含更直接的 `cancellation_policy.md`。

根因：

已发货后的取消、拒收和售后处理，与退货退款政策存在语义重叠。原取消政策虽然包含“已发货后通常不能直接取消、可拒收”的内容，但该信息位于较泛化的“标准流程”段落中，不利于 BM25 和模型在 TopK 证据中识别最直接的业务阶段。

修复：

- 在 `cancellation_policy.md` 中新增“已发货订单的取消、拒收与售后处理”小节，以自然业务语言补充“发货、出库、寄出、拒收、改变主意、不想要了”等常见表达。
- 强化系统 Prompt，要求回答时优先引用直接覆盖用户核心动作和业务阶段的政策 chunk。
- 补充回归测试 `test_shipped_cancellation_question_retrieves_cancellation_policy`，验证 BM25 Top3 召回 `cancellation_policy.md`。
- 补充回归测试 `test_citation_should_prefer_direct_business_stage_evidence`，用 stub LLM 验证当证据包包含取消政策时，引用取消政策可通过引用校验并进入最终 citations。

## 边界

- 引用来自检索证据，不代表自动验证答案语义完全正确。
- Prompt 约束可以降低模型误判概率，但真实模型输出仍需要 live acceptance、离线评测和人工抽检共同验证。
- 本次修复没有新增业务功能，没有进入 LangGraph、FastAPI、Agent 路由或订单级自动决策。
