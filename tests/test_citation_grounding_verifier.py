"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

from app.schemas.policy_qa_schema import PolicyGenerationResult
from app.services.citation_grounding_verifier import verify_policy_citations


def build_retrieved_chunks() -> list[dict]:
    """
    构造测试用检索结果。

    参数：
        无。

    返回：
        list[dict]：包含两个模拟 chunk。

    用途：
        让引用校验测试不依赖真实检索。
    """
    return [
        {"chunk_id": "chunk_1", "source_file": "a.md", "section_title": "规则"},
        {"chunk_id": "chunk_2", "source_file": "b.md", "section_title": "边界"},
    ]


# 这个测试验证：合法引用可以通过校验。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_valid_citation_passes() -> None:
    """
    验证模型引用来自本次检索证据时通过。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认正常引用不会被误判为失败。
    """
    generation_result = PolicyGenerationResult(
        answer="依据政策，可以这样处理。",
        cited_chunk_ids=["chunk_1"],
        needs_human_review=False,
        missing_information=[],
    )

    result = verify_policy_citations(generation_result, build_retrieved_chunks())

    assert result["passed"] is True
    assert result["valid_citation_ids"] == ["chunk_1"]


# 这个测试验证：模型引用不存在 chunk 时校验失败。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_invalid_citation_fails() -> None:
    """
    验证不存在的 chunk_id 会被标记为 invalid。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        防止模型引用本次证据之外的政策片段。
    """
    generation_result = PolicyGenerationResult(
        answer="引用了不存在的政策。",
        cited_chunk_ids=["not_exist"],
        needs_human_review=False,
        missing_information=[],
    )

    result = verify_policy_citations(generation_result, build_retrieved_chunks())

    assert result["passed"] is False
    assert result["invalid_citation_ids"] == ["not_exist"]


# 这个测试验证：模型返回空引用时校验失败。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_empty_citation_fails() -> None:
    """
    验证空引用列表不能通过校验。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确保回答至少可追溯到一个本次检索证据。
    """
    generation_result = PolicyGenerationResult(
        answer="没有引用。",
        cited_chunk_ids=[],
        needs_human_review=False,
        missing_information=[],
    )

    result = verify_policy_citations(generation_result, build_retrieved_chunks())

    assert result["passed"] is False
    assert "模型未提供任何引用。" in result["warnings"]
