"""
【文件作用】
本文件是项目中的 Python 模块，用于支撑当前目录对应的 Agent、RAG、Tool、API 或工程化能力。

【在项目中的位置】
它会被项目内的服务、脚本或测试按需导入。请结合文件名和所在目录理解具体调用关系。

【主要输入与输出】
输入和输出取决于具体函数。本注释只解释阅读路径，不改变业务逻辑、数据库、LLM 或 API 行为。
"""

# ============================================================
# 【核心文件分区】
# 1. 路径与依赖：导入本文件需要的模块。
# 2. 数据结构与辅助函数：定义本模块内部复用的工具。
# 3. 核心流程：实现本文件最重要的业务或工程能力。
# 4. 边界与阅读重点：说明副作用、异常和学习入口。
# ============================================================


import re
import time
from collections.abc import Callable
from typing import Any, TypeVar


T = TypeVar("T")
ORDER_ID_PATTERN = re.compile(r"\bORD\d{5}\b", re.IGNORECASE)


def mask_order_id(order_id: str | None) -> str | None:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    if not order_id:
        return None
    if ORDER_ID_PATTERN.fullmatch(order_id):
        return "ORD***"
    return "***"


def mask_order_ids_in_text(value: str | None) -> str | None:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    if value is None:
        return None
    return ORDER_ID_PATTERN.sub("ORD***", value)


def measure_tool_call(tool_name: str, func: Callable[..., T], *args: Any, **kwargs: Any) -> tuple[T, dict[str, Any]]:
    """
    统计真实 Tool 调用耗时。
    """
    start_time = time.perf_counter()
    try:
        result = func(*args, **kwargs)
    except Exception as error:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        trace = {
            "step": tool_name,
            "status": "error",
            "latency_ms": latency_ms,
            "error_type": type(error).__name__,
        }
        raise ToolCallError(trace, error) from error

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return result, {"step": tool_name, "status": "success", "latency_ms": latency_ms}


class ToolCallError(Exception):
    """
    携带 Tool 失败轨迹的包装异常。
    """

    def __init__(self, trace: dict[str, Any], original_error: Exception) -> None:
        """
        本函数是当前模块的辅助或核心步骤。
        
        参数：
            见函数签名。
        
        返回：
            见调用方使用的结构化结果。
        
        副作用：
            不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
        """
        super().__init__(str(original_error))
        self.trace = trace
        self.original_error = original_error


def summarize_tool_latency(tool_trace: list[dict[str, Any]]) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    tool_events = [
        event for event in tool_trace
        if isinstance(event.get("latency_ms"), (int, float))
    ]
    return {
        "total_tool_latency_ms": round(sum(float(event["latency_ms"]) for event in tool_events), 2),
        "tool_count": len(tool_events),
    }


def compact_tool_trace_for_log(tool_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    compact_events = []
    for event in tool_trace:
        if "latency_ms" not in event:
            continue
        compact_events.append(
            {
                "step": event.get("step"),
                "status": event.get("status"),
                "latency_ms": event.get("latency_ms"),
            }
        )
    return compact_events

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
