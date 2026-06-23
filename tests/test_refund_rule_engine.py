"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

from typing import Any

from app.config import DEMO_REFERENCE_DATETIME
from app.services.refund_rule_engine import evaluate_refund_eligibility


def build_base_order(**overrides: Any) -> dict[str, Any]:
    """
    构造可直接传给规则引擎的模拟订单。

    参数：
        overrides：需要覆盖的订单字段。

    返回：
        dict[str, Any]：模拟订单事实字典。

    用途：
        让规则引擎测试不依赖数据库，直接验证业务规则本身。
    """
    order = {
        "order_id": "TEST_ORDER",
        "payment_status": "paid",
        "shipping_status": "delivered",
        "refund_status": "none",
        "is_opened": False,
        "has_quality_issue": False,
        "delivery_time": "2026-06-18 12:00:00",
    }
    order.update(overrides)
    return order


# 这个测试验证：ORD10001 对应的未付款订单不适用退款。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_unpaid_order_is_not_applicable() -> None:
    """
    验证未付款订单返回 UNPAID_ORDER。

    参数：
        无。

    返回：
        None：pytest 会根据断言判断测试是否通过。

    用途：
        确认没有实际支付金额的订单不会进入退款流程。
    """
    order = build_base_order(
        order_id="ORD10001",
        payment_status="unpaid",
        shipping_status="unshipped",
        delivery_time=None,
    )

    result = evaluate_refund_eligibility(order, DEMO_REFERENCE_DATETIME)

    assert result["decision"] == "not_applicable"
    assert result["eligible"] is False
    assert result["reason_code"] == "UNPAID_ORDER"


# 这个测试验证：ORD10004 对应的签收 3 天、未拆封、无质量问题订单可退货退款。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_non_quality_unopened_within_7_days_is_eligible() -> None:
    """
    验证签收 3 天且未拆封的非质量问题订单可退货退款。

    参数：
        无。

    返回：
        None：pytest 会根据断言判断测试是否通过。

    用途：
        确认 7 天无理由退货规则可以正确命中。
    """
    order = build_base_order(
        order_id="ORD10004",
        delivery_time="2026-06-18 12:00:00",
        is_opened=False,
        has_quality_issue=False,
    )

    result = evaluate_refund_eligibility(order, DEMO_REFERENCE_DATETIME)

    assert result["decision"] == "eligible"
    assert result["eligible"] is True
    assert result["refund_type"] == "return_and_refund"
    assert result["reason_code"] == "NON_QUALITY_WITHIN_7_DAYS_UNOPENED"
    assert result["days_since_delivery"] == 3


# 这个测试验证：ORD10008 对应的已退款订单不可重复申请退款。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_refunded_order_is_not_applicable() -> None:
    """
    验证已退款订单返回 ALREADY_REFUNDED。

    参数：
        无。

    返回：
        None：pytest 会根据断言判断测试是否通过。

    用途：
        确认规则引擎会阻止重复退款。
    """
    order = build_base_order(
        order_id="ORD10008",
        refund_status="refunded",
    )

    result = evaluate_refund_eligibility(order, DEMO_REFERENCE_DATETIME)

    assert result["decision"] == "not_applicable"
    assert result["eligible"] is False
    assert result["reason_code"] == "ALREADY_REFUNDED"


# 这个测试验证：ORD10009 对应的已取消订单不适用重复退款判断。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_cancelled_order_is_not_applicable() -> None:
    """
    验证已取消订单返回 ORDER_CANCELLED。

    参数：
        无。

    返回：
        None：pytest 会根据断言判断测试是否通过。

    用途：
        确认已经取消的订单不会继续进入普通退款资格判断。
    """
    order = build_base_order(
        order_id="ORD10009",
        shipping_status="unshipped",
        refund_status="cancelled",
        delivery_time=None,
    )

    result = evaluate_refund_eligibility(order, DEMO_REFERENCE_DATETIME)

    assert result["decision"] == "not_applicable"
    assert result["eligible"] is False
    assert result["reason_code"] == "ORDER_CANCELLED"


# 这个测试验证：ORD10005 对应的签收 10 天订单超过非质量 7 天退货期。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_non_quality_over_7_days_is_not_eligible() -> None:
    """
    验证签收 10 天的非质量问题订单不可按 7 天无理由退货。

    参数：
        无。

    返回：
        None：pytest 会根据断言判断测试是否通过。

    用途：
        确认超过 7 天后，非质量问题退货退款不再符合条件。
    """
    order = build_base_order(
        order_id="ORD10005",
        delivery_time="2026-06-11 12:00:00",
        is_opened=False,
        has_quality_issue=False,
    )

    result = evaluate_refund_eligibility(order, DEMO_REFERENCE_DATETIME)

    assert result["decision"] == "not_eligible"
    assert result["eligible"] is False
    assert result["reason_code"] == "NON_QUALITY_OVER_7_DAYS"
    assert result["days_since_delivery"] == 10


# 这个测试验证：ORD10006 对应的已拆封且无质量问题订单不支持退货。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_opened_non_quality_product_is_not_eligible() -> None:
    """
    验证已拆封且无质量问题时不支持非质量退货。

    参数：
        无。

    返回：
        None：pytest 会根据断言判断测试是否通过。

    用途：
        确认规则会考虑商品是否影响二次销售。
    """
    order = build_base_order(
        order_id="ORD10006",
        delivery_time="2026-06-19 12:00:00",
        is_opened=True,
        has_quality_issue=False,
    )

    result = evaluate_refund_eligibility(order, DEMO_REFERENCE_DATETIME)

    assert result["decision"] == "not_eligible"
    assert result["eligible"] is False
    assert result["reason_code"] == "NON_QUALITY_OPENED_PRODUCT"


# 这个测试验证：ORD10007 对应的质量问题 15 天内订单可退款或换货。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_quality_issue_within_15_days_is_eligible() -> None:
    """
    验证质量问题在签收后 15 天内可退款或换货。

    参数：
        无。

    返回：
        None：pytest 会根据断言判断测试是否通过。

    用途：
        确认质量问题规则优先于是否拆封。
    """
    order = build_base_order(
        order_id="ORD10007",
        delivery_time="2026-06-11 12:00:00",
        is_opened=True,
        has_quality_issue=True,
    )

    result = evaluate_refund_eligibility(order, DEMO_REFERENCE_DATETIME)

    assert result["decision"] == "eligible"
    assert result["eligible"] is True
    assert result["refund_type"] == "quality_refund_or_exchange"
    assert result["reason_code"] == "QUALITY_ISSUE_WITHIN_15_DAYS"
    assert result["days_since_delivery"] == 10


# 这个测试验证：ORD10010 对应的质量问题超过 15 天需要转人工或保修。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_quality_issue_over_15_days_needs_manual_review() -> None:
    """
    验证质量问题超过 15 天时返回 manual_review。

    参数：
        无。

    返回：
        None：pytest 会根据断言判断测试是否通过。

    用途：
        确认超出售后期的问题不会被规则引擎直接判定可退款。
    """
    order = build_base_order(
        order_id="ORD10010",
        delivery_time="2026-06-03 12:00:00",
        is_opened=True,
        has_quality_issue=True,
    )

    result = evaluate_refund_eligibility(order, DEMO_REFERENCE_DATETIME)

    assert result["decision"] == "manual_review"
    assert result["eligible"] is False
    assert result["reason_code"] == "QUALITY_ISSUE_OVER_15_DAYS"
    assert result["days_since_delivery"] == 18


# 这个测试验证：缺少关键字段或字段异常时，规则引擎返回 manual_review 而不是崩溃。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_invalid_order_data_returns_manual_review() -> None:
    """
    验证缺少关键字段的模拟订单返回 manual_review。

    参数：
        无。

    返回：
        None：pytest 会根据断言判断测试是否通过。

    用途：
        确认规则引擎面对坏数据时可解释地降级到人工处理。
    """
    order = {
        "order_id": "BROKEN_ORDER",
        "payment_status": "paid",
        "shipping_status": "delivered",
        "refund_status": "none",
    }

    result = evaluate_refund_eligibility(order, DEMO_REFERENCE_DATETIME)

    assert result["decision"] == "manual_review"
    assert result["eligible"] is False
    assert result["reason_code"] == "INSUFFICIENT_OR_INVALID_ORDER_DATA"
