"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

from app.retrieval.faiss_policy_retriever import FAISSPolicyRetriever
from app.retrieval.policy_index_manager import build_policy_index
from app.retrieval.vector_index_manager import build_vector_index, load_vector_index


def build_dense_retriever_for_test() -> FAISSPolicyRetriever:
    """
    构建测试用 Dense 检索器。

    参数：
        无。

    返回：
        FAISSPolicyRetriever：可直接用于测试的 Dense 检索器。

    用途：
        避免每个测试手工重复拼装索引和 chunk。
    """
    build_policy_index()
    build_vector_index()
    faiss_index, policy_chunk_list, vector_manifest = load_vector_index()
    return FAISSPolicyRetriever(faiss_index, policy_chunk_list, vector_manifest)


# 这个测试验证：FAISS 索引中的向量数量与 manifest 中的 chunk 数一致。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_faiss_index_count_matches_manifest() -> None:
    """
    验证 FAISS 索引 ntotal 与 manifest chunk_count 一致。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认向量索引和政策 chunk 顺序关系没有损坏。
    """
    build_policy_index()
    manifest = build_vector_index()
    faiss_index, policy_chunk_list, vector_manifest = load_vector_index()

    assert int(faiss_index.ntotal) == int(manifest["chunk_count"])
    assert len(policy_chunk_list) == int(vector_manifest["chunk_count"])


# 这个测试验证：耳机保修问题在 Dense Top3 中能命中发票保修政策。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_dense_retrieves_warranty_policy() -> None:
    """
    验证“耳机保修多久”在 Dense Top3 中命中 invoice_warranty_policy.md。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认语义检索能召回保修政策。
    """
    dense_retriever = build_dense_retriever_for_test()

    result_list = dense_retriever.retrieve("耳机保修多久", top_k=3)
    source_files = [result["source_file"] for result in result_list]

    assert "invoice_warranty_policy.md" in source_files
