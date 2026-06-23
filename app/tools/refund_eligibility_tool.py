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


import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# 直接运行 python app\tools\refund_eligibility_tool.py 时，
# Python 默认从 app/tools 目录开始找模块，可能找不到项目根目录下的 app 包。
# 这里用当前文件位置推导项目根目录，并加入导入路径，保证本地演示命令稳定可运行。
PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from app.services.refund_rule_engine import evaluate_refund_eligibility
from app.tools.order_tool import get_order


def build_order_not_found_result(order_id: str) -> dict[str, Any]:
    """
    构造订单不存在时的统一返回结果。

    参数：
        order_id：用户输入的订单号。

    返回：
        dict[str, Any]：JSON 可序列化的退款判断结果。

    用途：
        订单不存在时不抛出未处理异常，而是返回 Agent 可以继续处理的结构化结果。
    """
    return {
        "order_id": order_id,
        "decision": "manual_review",
        "eligible": False,
        "refund_type": "none",
        "reason_code": "ORDER_NOT_FOUND",
        "reason": "未找到该订单，请核对订单号后重试。",
        "days_since_delivery": None,
        "next_action": "请补充正确订单号，或转人工客服协助核实。",
        "policy_references": [],
        "order_facts": None,
    }


def build_database_error_result(order_id: str, error_message: str) -> dict[str, Any]:
    """
    构造数据库不可用时的统一返回结果。

    参数：
        order_id：用户输入的订单号。
        error_message：底层数据库错误提示。

    返回：
        dict[str, Any]：JSON 可序列化的退款判断结果。

    用途：
        当数据库尚未初始化时，说明发生了什么、可能原因和解决方式。
    """
    return {
        "order_id": order_id,
        "decision": "manual_review",
        "eligible": False,
        "refund_type": "none",
        "reason_code": "DATABASE_NOT_READY",
        "reason": f"无法读取模拟订单数据库。可能原因：{error_message}",
        "days_since_delivery": None,
        "next_action": "请先运行 python scripts\\init_demo_data.py 初始化模拟数据库。",
        "policy_references": [],
        "order_facts": None,
    }


def check_refund_eligibility(
    order_id: str,
    reference_datetime: datetime | None = None,
) -> dict[str, Any]:
    """
    查询订单并判断退款资格。

    参数：
        order_id：订单号，例如 "ORD10004"。
        reference_datetime：规则判断使用的参考时间；测试中传固定时间以保证可复现。

    返回：
        dict[str, Any]：统一退款资格判断结果。

    用途：
        给后续 Agent 提供一个可调用 Tool：输入订单号，输出可解释的退款资格结论。
    """
    if not order_id or not order_id.strip():
        return {
            "order_id": order_id,
            "decision": "manual_review",
            "eligible": False,
            "refund_type": "none",
            "reason_code": "EMPTY_ORDER_ID",
            "reason": "订单号为空，无法查询退款资格。",
            "days_since_delivery": None,
            "next_action": "请提供有效订单号，例如 ORD10004。",
            "policy_references": [],
            "order_facts": None,
        }

    cleaned_order_id = order_id.strip()

    try:
        # Tool 层只负责获取订单事实；退款规则必须交给规则引擎。
        # 这样可以避免数据库查询逻辑和业务判断逻辑混在一起。
        order = get_order(cleaned_order_id)
    except FileNotFoundError as database_error:
        return build_database_error_result(
            order_id=cleaned_order_id,
            error_message=str(database_error),
        )

    if order is None:
        return build_order_not_found_result(cleaned_order_id)

    refund_decision = evaluate_refund_eligibility(
        order=order,
        reference_datetime=reference_datetime,
    )
    return refund_decision


if __name__ == "__main__":
    # 以下 print 只用于本地学习演示，方便观察 Tool 的 JSON 输出。
    # 后续正式服务化时，应改为结构化日志和工具调用轨迹记录。
    demo_order_ids = [
        "ORD10002",
        "ORD10003",
        "ORD10004",
        "ORD10005",
        "ORD10006",
        "ORD10007",
        "ORD10010",
        "ORD99999",
    ]

    for demo_order_id in demo_order_ids:
        result = check_refund_eligibility(demo_order_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
