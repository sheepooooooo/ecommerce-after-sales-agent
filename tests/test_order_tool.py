"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

from app.tools.order_tool import create_ticket, get_order, list_tickets
from scripts.init_demo_data import initialize_database


# 这个测试验证：已存在订单可以被查询到，并且 ORD10003 是已发货未签收状态。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_get_existing_order() -> None:
    """
    验证 ORD10003 存在，且 shipping_status 为 shipped。

    参数：
        无。

    返回：
        None：pytest 会根据断言判断测试是否通过。

    用途：
        确认订单查询 Tool 能正确读取初始化脚本写入的模拟订单。
    """
    # 测试前先初始化数据库，避免旧数据或其他测试创建的工单影响结果。
    initialize_database()

    order = get_order("ORD10003")

    assert order is not None
    assert order["order_id"] == "ORD10003"
    assert order["shipping_status"] == "shipped"
    assert order["is_opened"] is False
    assert order["has_quality_issue"] is False


# 这个测试验证：查询不存在的订单时，Tool 返回 None，而不是抛出难懂异常。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_get_missing_order() -> None:
    """
    验证不存在的订单返回 None。

    参数：
        无。

    返回：
        None：pytest 会根据断言判断测试是否通过。

    用途：
        确认后续 Agent 面对无效订单号时，可以得到可判断的空结果。
    """
    initialize_database()

    order = get_order("ORD99999")

    assert order is None


# 这个测试验证：可以创建模拟售后工单，并且初始状态固定为 open。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_create_ticket() -> None:
    """
    验证可以创建工单，并检查工单状态为 open。

    参数：
        无。

    返回：
        None：pytest 会根据断言判断测试是否通过。

    用途：
        确认无法自动判断的问题可以被记录为人工处理工单。
    """
    initialize_database()

    ticket = create_ticket(
        order_id="ORD10003",
        issue_type="refund_dispute",
        description="用户表示商品存在异常，希望人工处理。",
    )

    assert ticket["ticket_id"] == 1
    assert ticket["order_id"] == "ORD10003"
    assert ticket["issue_type"] == "refund_dispute"
    assert ticket["ticket_status"] == "open"


# 这个测试验证：创建工单后，可以按订单号查询到对应工单。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_list_tickets_by_order() -> None:
    """
    验证创建后能按订单号查询到对应工单。

    参数：
        无。

    返回：
        None：pytest 会根据断言判断测试是否通过。

    用途：
        确认 list_tickets(order_id) 能筛选指定订单下的工单。
    """
    initialize_database()

    create_ticket(
        order_id="ORD10003",
        issue_type="shipping_problem",
        description="用户反馈物流长时间没有更新。",
    )
    create_ticket(
        order_id="ORD10004",
        issue_type="return_question",
        description="用户想了解退货退款条件。",
    )

    tickets = list_tickets("ORD10003")

    assert len(tickets) == 1
    assert tickets[0]["order_id"] == "ORD10003"
    assert tickets[0]["issue_type"] == "shipping_problem"
