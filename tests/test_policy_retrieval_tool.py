"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

from app.retrieval.policy_index_manager import build_policy_index
from app.tools.policy_retrieval_tool import retrieve_policy


# 这个测试验证：无关问题不会被强行匹配到任意政策。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_unrelated_question_returns_no_relevant_policy() -> None:
    """
    验证无关问题返回 has_relevant_policy = false。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认天气等无关问题不会被硬塞一个政策结果。
    """
    build_policy_index()

    result = retrieve_policy("今天上海会不会下雨？", retrieval_mode="bm25")

    assert result["success"] is True
    assert result["has_relevant_policy"] is False
    assert result["retrieved_chunks"] == []


# 这个测试验证：空 query 会返回清晰结构，不抛出未处理异常。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_empty_query_returns_clear_result() -> None:
    """
    验证空 query 返回可读结果。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认 Tool 面对空输入时仍保持 JSON 可序列化结构。
    """
    build_policy_index()

    result = retrieve_policy("", retrieval_mode="bm25")

    assert result["success"] is True
    assert result["has_relevant_policy"] is False
    assert result["error"] is None


# 这个测试验证：优惠券问题能通过 Tool 返回相关政策。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_tool_retrieves_coupon_policy() -> None:
    """
    验证退货优惠券问题能召回 coupon_policy.md。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认 Tool 能使用 BM25 检索服务返回政策来源。
    """
    build_policy_index()

    result = retrieve_policy("退货以后优惠券会退回来吗？", top_k=3, retrieval_mode="bm25")
    source_files = [
        retrieved_chunk["source_file"]
        for retrieved_chunk in result["retrieved_chunks"]
    ]

    assert result["success"] is True
    assert "coupon_policy.md" in source_files
