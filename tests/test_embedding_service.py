"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

import numpy as np

from app.retrieval.embedding_service import embed_single_text, embed_text_list


# 这个测试验证：Embedding 服务能返回二维 float32 向量。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_embed_text_list_returns_float32_matrix() -> None:
    """
    验证多文本编码结果是二维 float32 数组。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认文档向量可以直接写入 FAISS。
    """
    embedding_array = embed_text_list(["订单已经发货但不想要了", "耳机保修多久"])

    assert isinstance(embedding_array, np.ndarray)
    assert embedding_array.dtype == np.float32
    assert embedding_array.ndim == 2
    assert embedding_array.shape[0] == 2


# 这个测试验证：文档和 query 使用同一个模型时向量维度一致。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_query_and_document_embedding_dimension_match() -> None:
    """
    验证单条 query 和文档列表的向量维度一致。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认 FAISS 索引向量和 query 向量处在同一个向量空间。
    """
    query_embedding = embed_single_text("支付成功但订单还是待付款怎么办")
    document_embedding = embed_text_list(["支付扣款成功但订单状态未更新，需要人工核实。"])

    assert query_embedding.shape[1] == document_embedding.shape[1]
