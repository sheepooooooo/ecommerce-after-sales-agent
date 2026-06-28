"""
【文件作用】
本文件是项目中的 Python 模块，用于支撑当前目录对应的 Agent、RAG、Tool、API 或工程化能力。

【在项目中的位置】
它会被项目内的服务、脚本或测试按需导入。请结合文件名和所在目录理解具体调用关系。

【主要输入与输出】
输入和输出取决于具体函数。本注释只解释阅读路径，不改变业务逻辑、数据库、LLM 或 API 行为。
"""

from datetime import datetime
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


# 真实生产系统通常会使用当前时间，例如 datetime.now()。
# 但本项目是学习和测试用的模拟项目，如果直接依赖电脑当前日期，
# ORD10004 "签收后 3 天" 这样的场景会随着时间流逝不断变化。
# 因此这里使用固定模拟业务时间，让测试和演示结果长期稳定、可复现。
DEMO_REFERENCE_DATETIME = datetime(2026, 6, 21, 12, 0, 0)


# __file__ 指向 app/config.py。
# parent 是 app 目录，再 parent 一次就是项目根目录。
# 用这种方式推导路径，可以让脚本从任意终端目录运行时都找到同一批政策和索引文件。
PROJECT_ROOT = Path(__file__).resolve().parent.parent
POLICY_DIRECTORY = PROJECT_ROOT / "data" / "policies"
POLICY_INDEX_DIRECTORY = PROJECT_ROOT / "data" / "indexes"

# 当前阶段先做 BM25 检索基线。默认返回 3 条，最多允许返回 5 条，
# 避免一次返回过多政策片段影响后续 Agent 判断。
DEFAULT_POLICY_TOP_K = 3
MAX_POLICY_TOP_K = 5

# 本项目选择 BGE small 中文模型，是因为它相对轻量，适合学习项目和 CPU 环境先跑通语义检索。
# 首次运行时 sentence-transformers 可能需要联网从 Hugging Face 下载模型。
# 下载完成后，模型通常会缓存在 Hugging Face 本地缓存目录，后续运行会复用本地缓存。
# 当前用户设备主要按 CPU 环境考虑，因此本阶段优先保证稳定、可运行，不追求高并发性能。
EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
DEFAULT_POLICY_RETRIEVAL_MODE = "hybrid"
DEFAULT_DENSE_CANDIDATE_K = 8
DEFAULT_HYBRID_CANDIDATE_K = 8
RRF_K = 60
DEFAULT_DENSE_RELEVANCE_THRESHOLD = 0.50


def _parse_int_env(env_name: str, default: int, minimum: int | None = None) -> int:
    """
    解析整数环境变量，并在配置错误时给出清晰提示。
    """
    raw_value = os.getenv(env_name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        parsed_value = int(raw_value.strip())
    except ValueError as error:
        raise ValueError(f"{env_name} 必须是整数，例如 {default}。") from error
    if minimum is not None and parsed_value < minimum:
        raise ValueError(f"{env_name} 不能小于 {minimum}。")
    return parsed_value


def _parse_float_env(env_name: str, default: float, minimum: float | None = None) -> float:
    """
    解析浮点数环境变量，并在配置错误时给出清晰提示。
    """
    raw_value = os.getenv(env_name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        parsed_value = float(raw_value.strip())
    except ValueError as error:
        raise ValueError(f"{env_name} 必须是数字，例如 {default}。") from error
    if minimum is not None and parsed_value < minimum:
        raise ValueError(f"{env_name} 不能小于 {minimum}。")
    return parsed_value


def _parse_bool_env(env_name: str, default: bool) -> bool:
    """
    解析布尔环境变量。

    参数：
        env_name：环境变量名称。
        default：未配置时使用的默认值。
    返回：
        bool：解析后的布尔值。
    用途：
        避免在不同脚本中重复解析 true/false，并在配置错误时给出清晰提示。
    """
    raw_value = os.getenv(env_name)
    if raw_value is None or raw_value.strip() == "":
        return default

    normalized_value = raw_value.strip().lower()
    if normalized_value in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "n", "off"}:
        return False

    raise ValueError(f"{env_name} 必须是布尔值，例如 true 或 false。")


def get_llm_config(require_api_key: bool = True) -> dict[str, Any]:
    """
    读取 DeepSeek / OpenAI 兼容模型配置。

    参数：
        require_api_key：是否要求必须存在 DEEPSEEK_API_KEY。

    返回：
        dict[str, Any]：包含 api_key、base_url、model、timeout、temperature、enable_thinking。

    用途：
        Policy QA 需要模型生成，但密钥不能写进代码或日志，只能从环境变量读取。
    """
    # load_dotenv 只读取本地 .env，不会创建或覆盖真实密钥文件。
    load_dotenv(PROJECT_ROOT / ".env")

    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if require_api_key and not api_key:
        raise RuntimeError(
            "当前功能需要模型生成，但未检测到 DEEPSEEK_API_KEY。"
            "请复制 .env.example 为 .env，填入自己的 DEEPSEEK_API_KEY。"
            "不要把真实 API Key 写入 Python 文件、README、测试或日志。"
        )

    timeout_text = os.getenv("LLM_TIMEOUT_SECONDS", "45").strip()
    temperature_text = os.getenv("POLICY_QA_TEMPERATURE", "0.2").strip()

    try:
        timeout_seconds = float(timeout_text)
    except ValueError as error:
        raise ValueError("LLM_TIMEOUT_SECONDS 必须是数字，例如 45。") from error

    try:
        temperature = float(temperature_text)
    except ValueError as error:
        raise ValueError("POLICY_QA_TEMPERATURE 必须是数字，例如 0.2。") from error

    return {
        "api_key": api_key,
        "base_url": os.getenv("LLM_BASE_URL", "https://api.deepseek.com").strip(),
        "model": os.getenv("LLM_MODEL", "deepseek-v4-flash").strip(),
        "timeout_seconds": timeout_seconds,
        "temperature": temperature,
        "enable_thinking": _parse_bool_env("LLM_ENABLE_THINKING", False),
    }


def get_api_config() -> dict[str, Any]:
    """
    读取 FastAPI 服务配置。

    用途：
        API 服务化阶段需要从环境变量读取监听地址、日志滚动参数、并发保护和超时配置。
        这些配置不包含 API Key，也不会读取或打印真实密钥。
    """
    load_dotenv(PROJECT_ROOT / ".env")
    return {
        "host": os.getenv("API_HOST", "127.0.0.1").strip() or "127.0.0.1",
        "port": _parse_int_env("API_PORT", 8011, minimum=1),
        "debug": _parse_bool_env("APP_DEBUG", False),
        "log_level": os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        "log_max_bytes": _parse_int_env("LOG_MAX_BYTES", 5242880, minimum=1024),
        "log_backup_count": _parse_int_env("LOG_BACKUP_COUNT", 3, minimum=0),
        "max_concurrent_agent_requests": _parse_int_env(
            "MAX_CONCURRENT_AGENT_REQUESTS",
            3,
            minimum=1,
        ),
        "agent_request_timeout_seconds": _parse_float_env(
            "AGENT_REQUEST_TIMEOUT_SECONDS",
            60,
            minimum=0.1,
        ),
    }


def get_retry_config() -> dict[str, Any]:
    """
    读取只读外部调用的有限重试配置。

    当前仅用于政策问答中的 LLM 调用，不用于创建工单、SQLite 写库或退款业务判断。
    """
    load_dotenv(PROJECT_ROOT / ".env")
    return {
        "max_retries": _parse_int_env("READ_ONLY_RETRY_MAX_RETRIES", 2, minimum=0),
        "base_delay_seconds": _parse_float_env("READ_ONLY_RETRY_BASE_DELAY_SECONDS", 0.2, minimum=0),
        "backoff_multiplier": _parse_float_env("READ_ONLY_RETRY_BACKOFF_MULTIPLIER", 2.0, minimum=1.0),
    }
