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


import asyncio
import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.agent.after_sales_agent_service import run_after_sales_agent
from app.api.api_schemas import AgentRunRequest, AgentRunResponse, HealthResponse
from app.api.dependencies import get_policy_qa_callable
from app.api.exception_handlers import (
    build_error_response,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.config import get_api_config
from app.observability.logging_config import configure_logging, get_api_logger
from app.observability.trace_utils import (
    compact_tool_trace_for_log,
    mask_order_id,
)


API_VERSION = "0.1.0"
SERVICE_NAME = "ecommerce-after-sales-agent"

api_config = get_api_config()
agent_semaphore = asyncio.Semaphore(api_config["max_concurrent_agent_requests"])
configure_logging()

app = FastAPI(
    title="E-commerce After-sales Agent API",
    version=API_VERSION,
)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Callable[..., Any]) -> Response:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    request.state.api_start_time = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = getattr(request.state, "request_id", request_id)
    return response


@app.get("/health", response_model=HealthResponse)
async def health() -> dict[str, str]:
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
        "status": "ok",
        "service": SERVICE_NAME,
        "version": API_VERSION,
    }


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def _build_safe_agent_log(
    request: Request,
    response_body: dict[str, Any],
    http_status: int,
    api_latency_ms: float,
    agent_latency_ms: float | None,
    error_code: str | None = None,
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
    order_ids = response_body.get("debug", {}).get("all_detected_order_ids", [])
    first_order_id = order_ids[0] if order_ids else None
    return {
        "event": "agent_api_request",
        "request_id": response_body.get("request_id", getattr(request.state, "request_id", "unknown")),
        "endpoint": request.url.path,
        "http_status": http_status,
        "intent": response_body.get("intent"),
        "tool_used": response_body.get("tool_used"),
        "answer_status": response_body.get("answer_status"),
        "api_latency_ms": api_latency_ms,
        "agent_latency_ms": agent_latency_ms,
        "error_code": error_code,
        "query_length": len(response_body.get("user_query", "")),
        "masked_order_id": mask_order_id(first_order_id),
        "tool_trace": compact_tool_trace_for_log(response_body.get("tool_trace", [])),
    }


@app.post("/agent/run", response_model=AgentRunResponse)
async def run_agent_endpoint(
    payload: AgentRunRequest,
    request: Request,
    policy_qa_callable: Callable[..., dict[str, Any]] = Depends(get_policy_qa_callable),
) -> JSONResponse:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    request_id = payload.request_id or getattr(request.state, "request_id", str(uuid4()))
    request.state.request_id = request_id

    if agent_semaphore._value <= 0:
        api_latency_ms = round((time.perf_counter() - request.state.api_start_time) * 1000, 2)
        error_body = build_error_response(
            request_id=request_id,
            code="agent_busy",
            message="当前 Agent 请求较多，请稍后重试。",
        )
        get_api_logger().warning(
            {
                "event": "agent_api_busy",
                "request_id": request_id,
                "endpoint": request.url.path,
                "http_status": 503,
                "error_code": "agent_busy",
                "api_latency_ms": api_latency_ms,
                "agent_latency_ms": None,
            }
        )
        return JSONResponse(
            status_code=503,
            content=error_body,
            headers={"X-Request-ID": request_id},
        )

    await agent_semaphore.acquire()
    agent_start_time = time.perf_counter()
    try:
        try:
            agent_result = await asyncio.wait_for(
                asyncio.to_thread(
                    run_after_sales_agent,
                    payload.user_query,
                    payload.confirm_ticket_creation,
                    request_id,
                    policy_qa_callable,
                ),
                timeout=api_config["agent_request_timeout_seconds"],
            )
        except TimeoutError:
            api_latency_ms = round((time.perf_counter() - request.state.api_start_time) * 1000, 2)
            error_body = build_error_response(
                request_id=request_id,
                code="request_timeout",
                message="Agent 请求处理超时，请稍后重试。",
            )
            get_api_logger().error(
                {
                    "event": "agent_api_timeout",
                    "request_id": request_id,
                    "endpoint": request.url.path,
                    "http_status": 504,
                    "error_code": "request_timeout",
                    "api_latency_ms": api_latency_ms,
                    "agent_latency_ms": api_config["agent_request_timeout_seconds"] * 1000,
                }
            )
            return JSONResponse(
                status_code=504,
                content=error_body,
                headers={"X-Request-ID": request_id},
            )

        agent_latency_ms = round((time.perf_counter() - agent_start_time) * 1000, 2)
        api_latency_ms = round((time.perf_counter() - request.state.api_start_time) * 1000, 2)
        response_body = {
            **agent_result,
            "request_id": request_id,
            "api_latency_ms": api_latency_ms,
            "agent_latency_ms": agent_latency_ms,
            "api_version": API_VERSION,
        }
        get_api_logger().info(
            _build_safe_agent_log(
                request=request,
                response_body=response_body,
                http_status=200,
                api_latency_ms=api_latency_ms,
                agent_latency_ms=agent_latency_ms,
            )
        )
        return JSONResponse(
            status_code=200,
            content=response_body,
            headers={"X-Request-ID": request_id},
        )
    finally:
        agent_semaphore.release()

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
