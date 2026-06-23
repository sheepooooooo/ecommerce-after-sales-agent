"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

import pytest

from app.config import get_llm_config


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_llm_enable_thinking_defaults_to_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    验证默认关闭 thinking，降低政策问答 JSON 输出不稳定风险。
    """
    monkeypatch.delenv("LLM_ENABLE_THINKING", raising=False)

    config = get_llm_config(require_api_key=False)

    assert config["enable_thinking"] is False


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_llm_enable_thinking_accepts_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    验证可通过环境变量显式开启 thinking。
    """
    monkeypatch.setenv("LLM_ENABLE_THINKING", "true")

    config = get_llm_config(require_api_key=False)

    assert config["enable_thinking"] is True


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_llm_enable_thinking_rejects_invalid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    验证配置错误时返回清晰异常，而不是静默忽略。
    """
    monkeypatch.setenv("LLM_ENABLE_THINKING", "sometimes")

    with pytest.raises(ValueError, match="LLM_ENABLE_THINKING"):
        get_llm_config(require_api_key=False)
