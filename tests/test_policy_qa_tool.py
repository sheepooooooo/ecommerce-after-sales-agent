"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

from app.tools.policy_qa_tool import ask_policy_question


# 这个测试验证：空 query 不会导致未处理异常。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_policy_qa_tool_empty_query_is_structured() -> None:
    """
    验证空问题返回结构化 no_relevant_policy。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认 Tool 对异常输入保持 JSON 可序列化输出。
    """
    result = ask_policy_question("")

    assert result["success"] is True
    assert result["answer_status"] == "no_relevant_policy"


# 这个测试验证：非法 top_k 不会导致未处理异常。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_policy_qa_tool_invalid_top_k_is_structured() -> None:
    """
    验证非法 top_k 返回 generation_error。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认参数错误被 Tool 捕获为结构化结果。
    """
    result = ask_policy_question("耳机保修多久？", top_k=0)

    assert result["success"] is False
    assert result["answer_status"] == "generation_error"


# 这个测试验证：非法 retrieval_mode 不会导致未处理异常。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_policy_qa_tool_invalid_mode_is_structured() -> None:
    """
    验证非法检索模式返回结构化错误。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认 Tool 不会因为模式错误直接崩溃。
    """
    result = ask_policy_question("耳机保修多久？", retrieval_mode="wrong")

    assert result["success"] is False
    assert result["answer_status"] == "generation_error"
    assert result["error"] is not None
