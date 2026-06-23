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


from datetime import datetime
from typing import Any

from app.config import DEMO_REFERENCE_DATETIME


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def build_policy_reference(file_name: str, rule_text: str) -> dict[str, str]:
    """
    构造规则来源标识。

    参数：
        file_name：政策文档文件名。
        rule_text：对应的政策规则摘要。

    返回：
        dict[str, str]：JSON 可序列化的规则来源信息。

    用途：
        当前阶段只标记规则来源，不代表已经做了 RAG 检索。
    """
    return {
        "file": file_name,
        "rule": rule_text,
    }


def get_order_facts(order: dict[str, Any]) -> dict[str, Any]:
    """
    从订单字典中提取退款判断需要的关键事实。

    参数：
        order：订单查询 Tool 返回的订单字典。

    返回：
        dict[str, Any]：只包含规则判断关心的字段。

    用途：
        让返回结果里可以清楚看到本次判断基于哪些订单事实。
    """
    return {
        "payment_status": order.get("payment_status"),
        "shipping_status": order.get("shipping_status"),
        "refund_status": order.get("refund_status"),
        "is_opened": order.get("is_opened"),
        "has_quality_issue": order.get("has_quality_issue"),
        "delivery_time": order.get("delivery_time"),
    }


def build_refund_decision(
    order: dict[str, Any],
    decision: str,
    eligible: bool,
    refund_type: str,
    reason_code: str,
    reason: str,
    days_since_delivery: int | None,
    next_action: str,
    policy_references: list[dict[str, str]],
) -> dict[str, Any]:
    """
    组装统一退款资格判断结果。

    参数：
        order：订单事实字典。
        decision：判断结论，只能是 eligible、not_eligible、not_applicable、manual_review。
        eligible：是否具备当前规则下的退款资格。
        refund_type：退款类型，例如 return_and_refund。
        reason_code：机器可读的原因编码。
        reason：给用户或客服看的可读原因。
        days_since_delivery：签收后经过的自然日；无法计算时为 None。
        next_action：下一步建议。
        policy_references：规则来源标识列表。

    返回：
        dict[str, Any]：JSON 可序列化的统一结果。

    用途：
        避免每条规则手写不同结构，方便后续 Tool、API 或评测复用。
    """
    return {
        "order_id": order.get("order_id"),
        "decision": decision,
        "eligible": eligible,
        "refund_type": refund_type,
        "reason_code": reason_code,
        "reason": reason,
        "days_since_delivery": days_since_delivery,
        "next_action": next_action,
        "policy_references": policy_references,
        "order_facts": get_order_facts(order),
    }


def build_manual_review_for_invalid_data(
    order: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    """
    构造字段不足或字段异常时的转人工结果。

    参数：
        order：订单事实字典。
        reason：说明发生了什么、可能原因和建议处理方式。

    返回：
        dict[str, Any]：统一退款判断结果。

    用途：
        遇到未知状态、缺失日期或时间解析失败时，不让程序直接崩溃。
    """
    return build_refund_decision(
        order=order,
        decision="manual_review",
        eligible=False,
        refund_type="none",
        reason_code="INSUFFICIENT_OR_INVALID_ORDER_DATA",
        reason=reason,
        days_since_delivery=None,
        next_action="请转人工客服核实订单状态、签收时间和售后条件。",
        policy_references=[],
    )


def parse_delivery_datetime(delivery_time: Any) -> datetime | None:
    """
    解析订单签收时间。

    参数：
        delivery_time：订单中的签收时间字符串，通常格式为 YYYY-MM-DD HH:MM:SS。

    返回：
        datetime | None：解析成功返回 datetime；没有签收时间返回 None。

    用途：
        退款规则需要计算签收后经过了多少自然日。
    """
    if delivery_time is None:
        return None
    if not isinstance(delivery_time, str) or not delivery_time.strip():
        raise ValueError("delivery_time 缺失或不是有效字符串。")
    return datetime.strptime(delivery_time.strip(), "%Y-%m-%d %H:%M:%S")


def calculate_days_since_delivery(
    delivery_datetime: datetime,
    reference_datetime: datetime,
) -> int:
    """
    计算签收后经过的自然日。

    参数：
        delivery_datetime：订单签收时间。
        reference_datetime：规则判断使用的参考时间。

    返回：
        int：签收日期到参考日期之间的天数。

    用途：
        判断是否还在 7 天无理由退货期或 15 天质量问题售后期内。
    """
    days_since_delivery = (
        reference_datetime.date() - delivery_datetime.date()
    ).days
    return days_since_delivery


def evaluate_refund_eligibility(
    order: dict[str, Any],
    reference_datetime: datetime | None = None,
) -> dict[str, Any]:
    """
    根据订单事实判断退款资格。

    参数：
        order：订单事实字典，通常来自 get_order(order_id)。
        reference_datetime：规则判断使用的参考时间；测试中应传固定时间。

    返回：
        dict[str, Any]：统一退款资格判断结果。

    用途：
        提供确定性的退款规则判断，不调用 LLM，不读取数据库。
    """
    # 数据库查询和规则判断要拆开：数据库负责提供订单事实，规则引擎负责解释事实。
    # 这样规则可以独立单元测试，后续更换数据库或接入 Agent 时也不影响规则本身。
    if not isinstance(order, dict):
        return build_manual_review_for_invalid_data(
            order={},
            reason="订单数据不是有效字典，可能是上游 Tool 返回格式错误，请转人工核实。",
        )

    # 测试中要传入固定参考时间，不能直接依赖系统当前时间。
    # 如果使用 datetime.now()，同一条订单在不同日期运行会得到不同结论，测试不可复现。
    actual_reference_datetime = reference_datetime or DEMO_REFERENCE_DATETIME

    payment_status = order.get("payment_status")
    shipping_status = order.get("shipping_status")
    refund_status = order.get("refund_status")
    is_opened = order.get("is_opened")
    has_quality_issue = order.get("has_quality_issue")

    # 已取消订单不需要再进入退款资格判断，避免重复处理已经关闭的售后流程。
    if refund_status == "cancelled":
        return build_refund_decision(
            order=order,
            decision="not_applicable",
            eligible=False,
            refund_type="none",
            reason_code="ORDER_CANCELLED",
            reason="订单已经取消，不需要重复申请退款。",
            days_since_delivery=None,
            next_action="请确认订单取消结果，如有争议可转人工客服核实。",
            policy_references=[
                build_policy_reference(
                    "cancellation_policy.md",
                    "已取消订单无需重复申请取消或退款。",
                )
            ],
        )

    # 已退款订单不能重复退款，避免同一笔支付被重复处理。
    if refund_status == "refunded":
        return build_refund_decision(
            order=order,
            decision="not_applicable",
            eligible=False,
            refund_type="none",
            reason_code="ALREADY_REFUNDED",
            reason="订单已经完成退款，不可重复申请退款。",
            days_since_delivery=None,
            next_action="请查看原支付渠道到账情况，如未到账可转人工客服核实。",
            policy_references=[
                build_policy_reference(
                    "refund_return_policy.md",
                    "已退款订单不可重复申请退款。",
                )
            ],
        )

    # 未付款订单没有实际支付金额，因此无需退款。
    if payment_status == "unpaid":
        return build_refund_decision(
            order=order,
            decision="not_applicable",
            eligible=False,
            refund_type="none",
            reason_code="UNPAID_ORDER",
            reason="订单尚未支付，没有实际扣款，因此无需申请退款。",
            days_since_delivery=None,
            next_action="无需退款；如不想购买，可以不继续支付。",
            policy_references=[
                build_policy_reference(
                    "cancellation_policy.md",
                    "未付款订单无需申请退款或取消付款。",
                )
            ],
        )

    if payment_status != "paid":
        return build_manual_review_for_invalid_data(
            order=order,
            reason="订单支付状态无法识别，可能是模拟数据缺少字段或状态值异常。",
        )

    if refund_status != "none":
        return build_manual_review_for_invalid_data(
            order=order,
            reason="订单退款状态无法识别，可能是模拟数据缺少字段或状态值异常。",
        )

    # 已付款但未发货时，商品还没有进入物流履约，可直接取消并退款。
    if shipping_status == "unshipped":
        return build_refund_decision(
            order=order,
            decision="eligible",
            eligible=True,
            refund_type="cancel_and_refund",
            reason_code="UNSHIPPED_ORDER",
            reason="订单已付款但尚未发货，符合直接取消订单并退款的条件。",
            days_since_delivery=None,
            next_action="可直接申请取消订单并原路退款。",
            policy_references=[
                build_policy_reference(
                    "cancellation_policy.md",
                    "已付款但尚未发货的订单，用户可直接申请取消。",
                )
            ],
        )

    # 已发货但未签收时，订单已经进入物流环节，不能直接按未发货取消。
    if shipping_status == "shipped":
        if order.get("delivery_time") is None:
            return build_refund_decision(
                order=order,
                decision="not_eligible",
                eligible=False,
                refund_type="none",
                reason_code="SHIPPED_NOT_DELIVERED",
                reason="订单已发货但尚未签收，当前不能直接申请退款。",
                days_since_delivery=None,
                next_action="可在签收前拒收，或签收后按退货政策申请售后。",
                policy_references=[
                    build_policy_reference(
                        "cancellation_policy.md",
                        "已发货订单不可直接取消；已发货但未签收可选择拒收。",
                    ),
                    build_policy_reference(
                        "shipping_policy.md",
                        "发货后订单状态为 shipped，本阶段只模拟物流状态。",
                    ),
                ],
            )
        return build_manual_review_for_invalid_data(
            order=order,
            reason="订单状态为 shipped 但存在签收时间，物流状态和签收时间不一致。",
        )

    if shipping_status != "delivered":
        return build_manual_review_for_invalid_data(
            order=order,
            reason="订单物流状态无法识别，可能是模拟数据缺少字段或状态值异常。",
        )

    try:
        delivery_datetime = parse_delivery_datetime(order.get("delivery_time"))
    except ValueError:
        return build_manual_review_for_invalid_data(
            order=order,
            reason="订单签收时间无法解析，可能是 delivery_time 缺失或格式不是 YYYY-MM-DD HH:MM:SS。",
        )

    if delivery_datetime is None:
        return build_manual_review_for_invalid_data(
            order=order,
            reason="订单状态为已签收，但缺少 delivery_time，无法计算售后期限。",
        )

    days_since_delivery = calculate_days_since_delivery(
        delivery_datetime=delivery_datetime,
        reference_datetime=actual_reference_datetime,
    )

    if days_since_delivery < 0:
        return build_manual_review_for_invalid_data(
            order=order,
            reason="订单签收时间晚于参考时间，可能是模拟数据日期配置错误。",
        )

    if not isinstance(is_opened, bool) or not isinstance(has_quality_issue, bool):
        return build_manual_review_for_invalid_data(
            order=order,
            reason="订单拆封状态或质量问题字段不是布尔值，无法安全判断退款资格。",
        )

    # 已签收且存在质量问题时，15 个自然日内可申请退货退款或换货。
    if has_quality_issue is True:
        if days_since_delivery <= 15:
            return build_refund_decision(
                order=order,
                decision="eligible",
                eligible=True,
                refund_type="quality_refund_or_exchange",
                reason_code="QUALITY_ISSUE_WITHIN_15_DAYS",
                reason=(
                    f"订单已签收 {days_since_delivery} 天，用户报告存在质量问题，"
                    "符合 15 天内质量问题退货退款或换货条件。"
                ),
                days_since_delivery=days_since_delivery,
                next_action="请提交质量问题售后申请，可选择退货退款或换货。",
                policy_references=[
                    build_policy_reference(
                        "refund_return_policy.md",
                        "质量问题：签收后 15 个自然日内，可申请退货退款或换货。",
                    )
                ],
            )
        return build_refund_decision(
            order=order,
            decision="manual_review",
            eligible=False,
            refund_type="none",
            reason_code="QUALITY_ISSUE_OVER_15_DAYS",
            reason=(
                f"订单已签收 {days_since_delivery} 天，已超出 15 天质量问题退货退款期。"
            ),
            days_since_delivery=days_since_delivery,
            next_action="已超出质量问题退货退款期，建议转人工或进入保修流程。",
            policy_references=[
                build_policy_reference(
                    "refund_return_policy.md",
                    "质量问题：签收后 15 个自然日内，可申请退货退款或换货。",
                ),
                build_policy_reference(
                    "invoice_warranty_policy.md",
                    "数码商品提供 12 个月保修，保修问题可能需要转人工处理。",
                ),
            ],
        )

    # 已签收、无质量问题、未拆封时，7 个自然日内可走非质量退货退款。
    if has_quality_issue is False and is_opened is False:
        if days_since_delivery <= 7:
            return build_refund_decision(
                order=order,
                decision="eligible",
                eligible=True,
                refund_type="return_and_refund",
                reason_code="NON_QUALITY_WITHIN_7_DAYS_UNOPENED",
                reason=(
                    f"订单已签收 {days_since_delivery} 天，商品未拆封且无质量问题，"
                    "符合 7 天无理由退货退款条件。"
                ),
                days_since_delivery=days_since_delivery,
                next_action="请提交退货退款申请，并保持商品、包装和配件完整。",
                policy_references=[
                    build_policy_reference(
                        "refund_return_policy.md",
                        "非质量问题：签收后 7 个自然日内，商品未拆封且配件包装齐全，可申请退货退款。",
                    )
                ],
            )
        return build_refund_decision(
            order=order,
            decision="not_eligible",
            eligible=False,
            refund_type="none",
            reason_code="NON_QUALITY_OVER_7_DAYS",
            reason=(
                f"订单已签收 {days_since_delivery} 天，已超过 7 天无理由退货退款期限。"
            ),
            days_since_delivery=days_since_delivery,
            next_action="当前不支持非质量问题退货退款，如有特殊情况可转人工客服咨询。",
            policy_references=[
                build_policy_reference(
                    "refund_return_policy.md",
                    "非质量问题：签收后 7 个自然日内，商品未拆封且配件包装齐全，可申请退货退款。",
                )
            ],
        )

    # 已签收、无质量问题、已拆封时，可能影响二次销售，不符合无理由退货条件。
    if has_quality_issue is False and is_opened is True:
        return build_refund_decision(
            order=order,
            decision="not_eligible",
            eligible=False,
            refund_type="none",
            reason_code="NON_QUALITY_OPENED_PRODUCT",
            reason="商品已拆封且无质量问题，可能影响二次销售，不符合 7 天无理由退货条件。",
            days_since_delivery=days_since_delivery,
            next_action="当前不支持非质量问题退货，如有争议可转人工客服核实。",
            policy_references=[
                build_policy_reference(
                    "refund_return_policy.md",
                    "商品已经使用、明显影响二次销售时，非质量问题不支持退货。",
                )
            ],
        )

    return build_manual_review_for_invalid_data(
        order=order,
        reason="订单字段组合无法匹配当前模拟退款规则，请转人工客服核实。",
    )

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
