"""
【文件作用】
本文件是项目中的 Python 模块，用于支撑当前目录对应的 Agent、RAG、Tool、API 或工程化能力。

【在项目中的位置】
它会被项目内的服务、脚本或测试按需导入。请结合文件名和所在目录理解具体调用关系。

【主要输入与输出】
输入和输出取决于具体函数。本注释只解释阅读路径，不改变业务逻辑、数据库、LLM 或 API 行为。
"""

import json
import sys
import time
from pathlib import Path
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from app.config import get_llm_config
from app.services.error_taxonomy import ErrorCategory


class LLMClientError(RuntimeError):
    """LLM client error carrying a stable, non-secret category."""

    def __init__(self, message: str, error_category: str) -> None:
        super().__init__(message)
        self.error_category = error_category


def get_deepseek_client() -> OpenAI:
    """
    创建 DeepSeek OpenAI 兼容客户端。

    参数：
        无。

    返回：
        OpenAI：已配置 base_url、api_key、timeout 的客户端。

    用途：
        将密钥和模型服务地址读取集中在一处，避免业务代码写死模型配置。
    """
    llm_config = get_llm_config(require_api_key=True)
    return OpenAI(
        api_key=llm_config["api_key"],
        base_url=llm_config["base_url"],
        timeout=llm_config["timeout_seconds"],
    )


def parse_json_object(raw_text: str) -> dict[str, Any]:
    """
    解析模型返回的 JSON 文本。

    参数：
        raw_text：模型返回的原始文本。

    返回：
        dict[str, Any]：解析后的 JSON 对象。

    用途：
        模型必须返回 JSON object，解析失败时给出清晰错误。
    """
    try:
        parsed_object = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise ValueError(f"模型返回内容不是合法 JSON：{error}") from error
    if not isinstance(parsed_object, dict):
        raise ValueError("模型返回 JSON 不是对象类型。")
    return parsed_object


def generate_policy_answer(messages: list[dict[str, str]]) -> dict[str, Any]:
    """
    调用 DeepSeek 生成政策问答 JSON。

    参数：
        messages：OpenAI chat messages。

    返回：
        dict[str, Any]：包含 raw_text、parsed、model、latency_ms。

    用途：
        给 policy_qa_service 提供可替换、可 mock 的模型生成入口。
    """
    llm_config = get_llm_config(require_api_key=True)
    client = get_deepseek_client()
    start_time = time.perf_counter()
    request_kwargs: dict[str, Any] = {
        "model": llm_config["model"],
        "messages": messages,
        "temperature": llm_config["temperature"],
        "response_format": {"type": "json_object"},
    }
    if not llm_config["enable_thinking"]:
        request_kwargs["extra_body"] = {"enable_thinking": False}

    try:
        response = client.chat.completions.create(**request_kwargs)
    except APITimeoutError as error:
        raise LLMClientError(
            "DeepSeek 调用超时，请检查网络或调大 LLM_TIMEOUT_SECONDS。",
            ErrorCategory.LLM_TIMEOUT.value,
        ) from error
    except APIConnectionError as error:
        raise LLMClientError(
            "DeepSeek 网络连接失败，请检查网络、代理或 base_url。",
            ErrorCategory.LLM_NETWORK_ERROR.value,
        ) from error
    except APIStatusError as error:
        category = (
            ErrorCategory.LLM_RATE_LIMIT.value
            if error.status_code in {429, 500, 502, 503, 504}
            else ErrorCategory.LLM_CONFIGURATION_ERROR.value
        )
        raise LLMClientError(
            f"DeepSeek API 返回错误状态：{error.status_code}。"
            "请检查 API Key、模型名称、账户状态、JSON Object 输出模式或 LLM_ENABLE_THINKING 参数兼容性。",
            category,
        ) from error
    except Exception as error:
        raise LLMClientError(
            "DeepSeek 调用失败。可能原因包括 OpenAI SDK 版本或 DeepSeek 参数不兼容、模型不可用、"
            "网络异常或返回格式异常。请检查 LLM_ENABLE_THINKING、LLM_MODEL 和 SDK 版本。",
            ErrorCategory.INTERNAL_ERROR.value,
        ) from error

    latency_ms = (time.perf_counter() - start_time) * 1000
    raw_text = response.choices[0].message.content or ""
    parsed = parse_json_object(raw_text)

    return {
        "raw_text": raw_text,
        "parsed": parsed,
        "model": llm_config["model"],
        "latency_ms": round(latency_ms, 4),
    }


if __name__ == "__main__":
    print("DeepSeek 客户端模块。请运行：python scripts\\check_llm_connection.py 检查连接。")
    print("安全提示：脚本不会打印任何 API Key。")
