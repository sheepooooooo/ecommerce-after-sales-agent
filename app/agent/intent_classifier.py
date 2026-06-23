"""
【文件作用】
本文件是项目中的 Python 模块，用于支撑当前目录对应的 Agent、RAG、Tool、API 或工程化能力。

【在项目中的位置】
它会被项目内的服务、脚本或测试按需导入。请结合文件名和所在目录理解具体调用关系。

【主要输入与输出】
输入和输出取决于具体函数。本注释只解释阅读路径，不改变业务逻辑、数据库、LLM 或 API 行为。
"""

# ============================================================
# 【核心文件分区】
# 1. 路径与依赖：导入本文件需要的模块。
# 2. 数据结构与辅助函数：定义本模块内部复用的工具。
# 3. 核心流程：实现本文件最重要的业务或工程能力。
# 4. 边界与阅读重点：说明副作用、异常和学习入口。
# ============================================================



def _contains_any(text: str, keywords: list[str]) -> bool:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    return any(keyword in text for keyword in keywords)


def classify_intent(user_query: str, order_id: str | None) -> dict:
    """
    按固定优先级分类售后意图，不调用 LLM。
    """
    query = (user_query or "").strip()
    normalized_query = query.lower()

    # 1. 高风险、隐私、账户安全、重复扣款和强投诉优先转人工。
    # 这些场景可能涉及账号安全、资金争议或敏感信息，不应由当前模拟 Agent 自动处理。
    human_handoff_keywords = [
        "账号被盗",
        "账户被盗",
        "银行卡",
        "重复扣款",
        "多扣",
        "隐私",
        "泄露",
        "报警",
        "起诉",
        "严重投诉",
    ]
    if _contains_any(normalized_query, human_handoff_keywords):
        return {
            "intent": "human_handoff",
            "confidence": "rule_based",
            "reason": "问题包含账户安全、资金争议、隐私或强投诉关键词，需要人工处理。",
            "requires_order_id": False,
        }

    # 2. 明确要求创建或提交工单时，进入工单确认流程。
    ticket_keywords = ["创建工单", "提交工单", "新建工单", "售后工单", "投诉工单"]
    if _contains_any(normalized_query, ticket_keywords):
        return {
            "intent": "create_ticket",
            "confidence": "rule_based",
            "reason": "问题明确要求创建或提交售后工单。",
            "requires_order_id": False,
        }

    # 优惠券退回、发票、保修等即使包含“退货”字样，也是在问通用政策。
    policy_before_refund_keywords = ["优惠券", "优惠劵", "发票", "保修", "积分"]
    if _contains_any(normalized_query, policy_before_refund_keywords):
        return {
            "intent": "policy_qa",
            "confidence": "rule_based",
            "reason": "问题包含售后政策咨询关键词。",
            "requires_order_id": False,
        }

    # 3. 退款、退货、换货进入退款资格 Tool。缺订单号时仍保留该 intent，便于追问。
    refund_keywords = ["退款", "退货", "退钱", "退回", "换货", "退换"]
    if _contains_any(normalized_query, refund_keywords):
        reason = "问题包含退款、退货或换货关键词"
        if order_id:
            reason += "且检测到订单号。"
        else:
            reason += "，但未检测到订单号。"
        return {
            "intent": "refund_eligibility",
            "confidence": "rule_based",
            "reason": reason,
            "requires_order_id": True,
        }

    # 4. 订单、物流、发货、到货状态查询进入订单查询 Tool。
    order_lookup_keywords = [
        "物流",
        "快递",
        "发货",
        "到货",
        "签收",
        "订单状态",
        "什么状态",
        "查订单",
        "查询订单",
        "帮我查",
        "现在是什么状态",
    ]
    if order_id or _contains_any(normalized_query, order_lookup_keywords):
        return {
            "intent": "order_lookup",
            "confidence": "rule_based",
            "reason": "问题包含订单号或订单/物流状态查询关键词。",
            "requires_order_id": True,
        }

    # 5. 政策类咨询进入政策问答 RAG。
    policy_keywords = [
        "支付",
        "取消订单",
        "拒收",
        "运费",
        "政策",
        "规则",
    ]
    if _contains_any(normalized_query, policy_keywords):
        return {
            "intent": "policy_qa",
            "confidence": "rule_based",
            "reason": "问题包含售后政策咨询关键词。",
            "requires_order_id": False,
        }

    # 6. 其他请求保持 unknown，不调用 LLM 或业务 Tool。
    return {
        "intent": "unknown",
        "confidence": "rule_based",
        "reason": "未匹配当前受控售后场景中的意图规则。",
        "requires_order_id": False,
    }

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
