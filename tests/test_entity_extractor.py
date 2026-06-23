"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

from app.agent.entity_extractor import extract_order_id, extract_order_ids


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_extract_order_id_case_insensitive() -> None:
    assert extract_order_id("ORD10003") == "ORD10003"
    assert extract_order_id("ord10003") == "ORD10003"
    assert extract_order_id("Ord10003") == "ORD10003"


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_extract_multiple_order_ids_records_all_and_picks_first() -> None:
    query = "请比较 ord10003 和 ORD10004 的物流状态"

    assert extract_order_id(query) == "ORD10003"
    assert extract_order_ids(query) == ["ORD10003", "ORD10004"]
