"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

from app.retrieval.policy_loader import build_all_policy_chunks, load_policy_documents


# 这个测试验证：政策目录中可以稳定加载 10 份 Markdown 文档。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_load_ten_policy_documents() -> None:
    """
    验证能加载 10 份政策文档。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认第三阶段 A 的政策知识库文件齐全。
    """
    policy_document_list = load_policy_documents()

    assert len(policy_document_list) == 10


# 这个测试验证：政策文档能按二级标题生成 chunk。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_build_chunks_by_markdown_headings() -> None:
    """
    验证按标题生成政策 chunk。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认切块保留了小节标题，而不是机械按字符数截断。
    """
    policy_chunk_list = build_all_policy_chunks()

    assert len(policy_chunk_list) >= 30
    assert all(policy_chunk.section_title for policy_chunk in policy_chunk_list)
    assert all(policy_chunk.source_file.endswith(".md") for policy_chunk in policy_chunk_list)


# 这个测试验证：退款政策切出的 chunk 中包含非质量问题相关规则。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_refund_policy_chunk_contains_non_quality_rule() -> None:
    """
    验证 refund_return_policy.md 生成的 chunk 包含非质量问题内容。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认核心退款规则没有在切块过程中丢失。
    """
    policy_chunk_list = build_all_policy_chunks()
    refund_chunk_contents = [
        policy_chunk.content
        for policy_chunk in policy_chunk_list
        if policy_chunk.source_file == "refund_return_policy.md"
    ]

    assert any("非质量问题" in chunk_content for chunk_content in refund_chunk_contents)
