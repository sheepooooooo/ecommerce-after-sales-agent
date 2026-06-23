"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

from app.agent.intent_classifier import classify_intent


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_refund_question_routes_to_refund_eligibility() -> None:
    result = classify_intent("ORD10004 可以退款吗", "ORD10004")

    assert result["intent"] == "refund_eligibility"
    assert result["requires_order_id"] is True


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_order_logistics_question_routes_to_order_lookup() -> None:
    result = classify_intent("ORD10003 的物流怎么样", "ORD10003")

    assert result["intent"] == "order_lookup"
    assert result["requires_order_id"] is True


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_policy_question_routes_to_policy_qa() -> None:
    result = classify_intent("耳机保修多久", None)

    assert result["intent"] == "policy_qa"
    assert result["requires_order_id"] is False


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_human_handoff_keywords_have_highest_priority() -> None:
    result = classify_intent("我的银行卡被重复扣款了，我要投诉", None)

    assert result["intent"] == "human_handoff"
