"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

from app.config import DEMO_REFERENCE_DATETIME
from app.tools.refund_eligibility_tool import check_refund_eligibility
from scripts.init_demo_data import initialize_database


# 这个测试验证：ORD10002 已付款未发货，可直接取消并退款。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_tool_unshipped_paid_order_is_eligible() -> None:
    """
    验证 ORD10002 返回 UNSHIPPED_ORDER。

    参数：
        无。

    返回：
        None：pytest 会根据断言判断测试是否通过。

    用途：
        确认 Tool 能查到订单，并复用规则引擎判断未发货退款资格。
    """
    initialize_database()

    result = check_refund_eligibility("ORD10002", DEMO_REFERENCE_DATETIME)

    assert result["decision"] == "eligible"
    assert result["eligible"] is True
    assert result["refund_type"] == "cancel_and_refund"
    assert result["reason_code"] == "UNSHIPPED_ORDER"


# 这个测试验证：ORD10003 已发货未签收，不能直接退款。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_tool_shipped_not_delivered_is_not_eligible() -> None:
    """
    验证 ORD10003 返回 SHIPPED_NOT_DELIVERED。

    参数：
        无。

    返回：
        None：pytest 会根据断言判断测试是否通过。

    用途：
        确认已发货未签收场景不会被误判为可直接取消退款。
    """
    initialize_database()

    result = check_refund_eligibility("ORD10003", DEMO_REFERENCE_DATETIME)

    assert result["decision"] == "not_eligible"
    assert result["eligible"] is False
    assert result["reason_code"] == "SHIPPED_NOT_DELIVERED"


# 这个测试验证：不存在的订单不会抛出未处理异常，而是返回 ORDER_NOT_FOUND。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_tool_missing_order_returns_order_not_found() -> None:
    """
    验证不存在订单返回 ORDER_NOT_FOUND。

    参数：
        无。

    返回：
        None：pytest 会根据断言判断测试是否通过。

    用途：
        确认 Agent 调用 Tool 时可以得到结构化失败结果。
    """
    initialize_database()

    result = check_refund_eligibility("ORD99999", DEMO_REFERENCE_DATETIME)

    assert result["decision"] == "manual_review"
    assert result["eligible"] is False
    assert result["reason_code"] == "ORDER_NOT_FOUND"
    assert result["order_facts"] is None
