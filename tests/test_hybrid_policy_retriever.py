"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

from pathlib import Path

import pytest

from app.retrieval.policy_index_manager import build_policy_index, get_policy_index_paths
from app.retrieval.vector_index_manager import build_vector_index, load_vector_index
from app.tools.policy_retrieval_tool import retrieve_policy


def build_all_indexes_for_test() -> None:
    """
    构建测试所需的全部政策索引。

    参数：
        无。

    返回：
        None。

    用途：
        保证测试不依赖手工先运行构建脚本。
    """
    build_policy_index()
    build_vector_index()


# 这个测试验证：口语化发货后不想收的问题在 Hybrid Top3 中命中取消政策。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_hybrid_retrieves_cancellation_policy_for_paraphrase() -> None:
    """
    验证 Hybrid 能召回 cancellation_policy.md。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认 BM25 + Dense 能处理较口语化的取消/拒收表达。
    """
    build_all_indexes_for_test()

    result = retrieve_policy(
        "包裹都寄出来了，我改变主意了怎么处理",
        top_k=3,
        retrieval_mode="hybrid",
    )
    source_files = [chunk["source_file"] for chunk in result["retrieved_chunks"]]

    assert "cancellation_policy.md" in source_files


# 这个测试验证：Hybrid 结果同时包含 BM25、Dense 和 RRF 分数字段。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_hybrid_result_contains_score_fields() -> None:
    """
    验证 Hybrid 返回 bm25_score、dense_score、rrf_score 字段。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认混合检索结果可解释。
    """
    build_all_indexes_for_test()

    result = retrieve_policy("退货以后优惠券会退回来吗？", retrieval_mode="hybrid")
    top_chunk = result["retrieved_chunks"][0]

    assert "bm25_score" in top_chunk
    assert "dense_score" in top_chunk
    assert "rrf_score" in top_chunk


# 这个测试验证：天气类无关问题在 Hybrid 模式下不应被强行判断为相关政策。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_hybrid_unrelated_question_has_no_relevant_policy() -> None:
    """
    验证天气类无关问题 has_relevant_policy 为 false。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认向量检索返回候选时，上层仍会做相关性判断。
    """
    build_all_indexes_for_test()

    result = retrieve_policy("我想问今天天气怎么样？", retrieval_mode="hybrid")

    assert result["success"] is True
    assert result["has_relevant_policy"] is False
    assert result["retrieved_chunks"] == []


# 这个测试验证：policy_chunks.jsonl 被修改后，旧向量 manifest 校验会失败并提示重建。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_vector_manifest_validation_fails_after_chunk_index_changes() -> None:
    """
    验证 chunk 索引变化后旧 vector manifest 校验失败。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认政策修改后必须重建向量索引，避免 chunk 与向量错位。
    """
    build_all_indexes_for_test()
    chunks_path = get_policy_index_paths()["chunks_path"]
    original_content = Path(chunks_path).read_text(encoding="utf-8")

    try:
        Path(chunks_path).write_text(
            original_content + "\n",
            encoding="utf-8",
        )
        with pytest.raises(RuntimeError, match="重新运行"):
            load_vector_index()
    finally:
        Path(chunks_path).write_text(original_content, encoding="utf-8")
        build_vector_index()


# 这个测试验证：空 query 和非法 retrieval_mode 不会导致未处理异常。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_empty_query_and_invalid_mode_are_structured_results() -> None:
    """
    验证空 query 和非法 retrieval_mode 返回结构化结果。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认 Tool 面对异常输入时保持 JSON 可序列化输出。
    """
    build_all_indexes_for_test()

    empty_result = retrieve_policy("", retrieval_mode="hybrid")
    invalid_mode_result = retrieve_policy("退货怎么处理", retrieval_mode="wrong_mode")

    assert empty_result["success"] is True
    assert empty_result["has_relevant_policy"] is False
    assert invalid_mode_result["success"] is False
    assert invalid_mode_result["error"] is not None
