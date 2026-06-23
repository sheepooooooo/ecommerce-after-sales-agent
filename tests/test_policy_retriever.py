"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

from app.retrieval.policy_index_manager import build_policy_index
from app.retrieval.policy_retriever import retrieve_policies


# 这个测试验证：发货后不想要的问题能召回订单取消政策。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_retrieve_cancellation_policy_for_shipped_order_question() -> None:
    """
    验证“订单发货后不想要了怎么办”能召回 cancellation_policy.md。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认 BM25 对取消、发货、拒收等关键词有基础召回能力。
    """
    build_policy_index()

    result = retrieve_policies("订单发货后不想要了怎么办", top_k=3, retrieval_mode="bm25")
    result_list = result["retrieved_chunks"]
    source_files = [result["source_file"] for result in result_list]

    assert "cancellation_policy.md" in source_files


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_shipped_cancellation_question_retrieves_cancellation_policy() -> None:
    """
    验证真实验收中的已发货取消问题能在 BM25 Top3 召回取消政策。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确保 Q3 的修复不依赖 LLM，也不通过固定 query 强制指定 source_file。
    """
    build_policy_index()

    result = retrieve_policies(
        "商品已经发货，但我临时不想要了怎么办？",
        top_k=3,
        retrieval_mode="bm25",
    )
    source_files = [retrieved_chunk["source_file"] for retrieved_chunk in result["retrieved_chunks"]]

    assert "cancellation_policy.md" in source_files


# 这个测试验证：保修问题能召回发票与保修政策。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_retrieve_warranty_policy_for_earphone_question() -> None:
    """
    验证“耳机保修多久”能召回 invoice_warranty_policy.md。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认 BM25 能命中数码商品保修相关政策。
    """
    build_policy_index()

    result = retrieve_policies("耳机保修多久", top_k=3, retrieval_mode="bm25")
    result_list = result["retrieved_chunks"]
    source_files = [result["source_file"] for result in result_list]

    assert "invoice_warranty_policy.md" in source_files


# 这个测试验证：非法 top_k 不会导致检索器崩溃。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_invalid_top_k_does_not_crash() -> None:
    """
    验证非法 top_k 会被安全处理。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认用户传入异常 top_k 时，程序仍返回结构化结果。
    """
    build_policy_index()

    result = retrieve_policies("退货优惠券会退吗", top_k=-1, retrieval_mode="bm25")
    result_list = result["retrieved_chunks"]

    assert isinstance(result_list, list)
    assert len(result_list) > 0
