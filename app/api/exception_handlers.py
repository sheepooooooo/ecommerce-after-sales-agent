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


import traceback
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_api_config
from app.observability.logging_config import get_api_logger


def _get_request_id(request: Request) -> str:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    return getattr(request.state, "request_id", request.headers.get("X-Request-ID", "unknown"))


def build_error_response(
    request_id: str,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    return {
        "success": False,
        "request_id": request_id,
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        },
    }


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    request_id = _get_request_id(request)
    details = [
        {
            "loc": list(error.get("loc", [])),
            "message": error.get("msg", "请求参数不合法"),
            "type": error.get("type"),
        }
        for error in exc.errors()
    ]
    logger = get_api_logger()
    logger.info(
        {
            "event": "api_validation_error",
            "request_id": request_id,
            "endpoint": request.url.path,
            "http_status": 422,
            "error_code": "validation_error",
            "details_count": len(details),
        }
    )
    return JSONResponse(
        status_code=422,
        content=build_error_response(
            request_id=request_id,
            code="validation_error",
            message="请求参数不合法",
            details=details,
        ),
        headers={"X-Request-ID": request_id},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    request_id = _get_request_id(request)
    api_config = get_api_config()
    log_event: dict[str, Any] = {
        "event": "api_unhandled_exception",
        "request_id": request_id,
        "endpoint": request.url.path,
        "http_status": 500,
        "error_code": "internal_server_error",
        "error_type": type(exc).__name__,
    }
    if api_config["debug"]:
        log_event["traceback"] = traceback.format_exc()
    get_api_logger().error(log_event)
    return JSONResponse(
        status_code=500,
        content=build_error_response(
            request_id=request_id,
            code="internal_server_error",
            message="服务内部错误，请稍后重试或联系人工处理。",
        ),
        headers={"X-Request-ID": request_id},
    )

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
