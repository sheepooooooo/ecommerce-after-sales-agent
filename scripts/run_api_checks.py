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


import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.init_demo_data import initialize_database


HOST = "127.0.0.1"
PORT = 8011
BASE_URL = f"http://{HOST}:{PORT}"
RESULTS_DIR = PROJECT_ROOT / "eval_results"
ACCEPTANCE_JSON = RESULTS_DIR / "agent_api_acceptance.json"
ACCEPTANCE_REPORT = RESULTS_DIR / "agent_api_acceptance_report.md"


def is_port_in_use(host: str, port: int) -> bool:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((host, port)) == 0


def request_json(path: str, payload: dict[str, Any] | None = None, method: str = "GET") -> tuple[int, dict[str, Any], str, float]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    url = f"{BASE_URL}{path}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    start_time = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            body = json.loads(response.read().decode("utf-8"))
            return response.status, body, response.headers.get("X-Request-ID", ""), latency_ms
    except urllib.error.HTTPError as error:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        body = json.loads(error.read().decode("utf-8"))
        return error.code, body, error.headers.get("X-Request-ID", ""), latency_ms


def wait_for_health() -> tuple[bool, dict[str, Any] | None]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            status_code, body, request_id, latency_ms = request_json("/health")
            if status_code == 200 and body.get("status") == "ok":
                return True, {
                    "http_status": status_code,
                    "body": body,
                    "request_id": request_id,
                    "latency_ms": latency_ms,
                }
        except Exception:
            time.sleep(0.5)
    return False, None


def run_scenario(name: str, payload: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    status_code, body, request_id, latency_ms = request_json("/agent/run", payload=payload, method="POST")
    passed = (
        status_code == 200
        and body.get("intent") == expected.get("intent")
        and body.get("tool_used") == expected.get("tool_used")
        and body.get("answer_status") == expected.get("answer_status")
    )
    return {
        "name": name,
        "http_status": status_code,
        "request_id": request_id or body.get("request_id"),
        "intent": body.get("intent"),
        "tool_used": body.get("tool_used"),
        "answer_status": body.get("answer_status"),
        "passed": passed,
        "latency_ms": latency_ms,
        "failure_reason": None if passed else f"expected={expected}, actual={body}",
    }


def write_outputs(result: dict[str, Any]) -> None:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ACCEPTANCE_JSON.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Agent API 一键验收报告",
        "",
        f"- 验收时间：{result['accepted_at']}",
        f"- 服务启动是否成功：{result['server_started']}",
        f"- 整体验收是否通过：{result['passed']}",
        "",
        "## 健康检查",
        "",
        f"- 结果：{result.get('health_check')}",
        "",
        "## 请求场景",
        "",
    ]
    for item in result["scenarios"]:
        lines.extend(
            [
                f"### {item['name']}",
                "",
                f"- HTTP 状态：{item['http_status']}",
                f"- request_id：{item['request_id']}",
                f"- intent：{item['intent']}",
                f"- tool_used：{item['tool_used']}",
                f"- answer_status：{item['answer_status']}",
                f"- 是否通过：{item['passed']}",
                f"- 耗时：{item['latency_ms']} ms",
                f"- 失败原因：{item['failure_reason']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 项目边界说明",
            "",
            "- 当前是本地单进程模拟业务服务，不是生产级高可用系统。",
            "- 当前并发保护仅是进程内基础保护，不是分布式限流。",
            "- 本脚本不测试 policy_qa，避免依赖真实 DeepSeek API Key。",
            "- 创建的是本地模拟工单，不执行真实退款或真实售后动作。",
        ]
    )
    ACCEPTANCE_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    accepted_at = datetime.now().replace(microsecond=0).isoformat()
    result: dict[str, Any] = {
        "accepted_at": accepted_at,
        "server_started": False,
        "health_check": None,
        "scenarios": [],
        "passed": False,
        "error": None,
    }
    process: subprocess.Popen | None = None

    try:
        if is_port_in_use(HOST, PORT):
            result["error"] = f"端口 {HOST}:{PORT} 已被占用，请停止已有服务后重试。"
            print(result["error"])
            return

        initialize_database()
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.api_server:app",
                "--host",
                HOST,
                "--port",
                str(PORT),
            ],
            cwd=PROJECT_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        server_started, health_check = wait_for_health()
        result["server_started"] = server_started
        result["health_check"] = health_check
        if not server_started:
            result["error"] = "服务未能在限定时间内通过 /health 检查。"
            return

        scenarios = [
            (
                "GET /health",
                None,
                {},
            ),
            (
                "ORD10003 现在是什么状态？",
                {"user_query": "ORD10003 现在是什么状态？"},
                {"intent": "order_lookup", "tool_used": "order_tool.get_order", "answer_status": "answered"},
            ),
            (
                "ORD10004 可以退款吗？",
                {"user_query": "ORD10004 可以退款吗？"},
                {
                    "intent": "refund_eligibility",
                    "tool_used": "refund_eligibility_tool.check_refund_eligibility",
                    "answer_status": "answered",
                },
            ),
            (
                "我想退款",
                {"user_query": "我想退款"},
                {"intent": "refund_eligibility", "tool_used": None, "answer_status": "missing_order_id"},
            ),
            (
                "请创建工单，订单号是 ORD10003（未确认）",
                {"user_query": "请创建工单，订单号是 ORD10003"},
                {"intent": "create_ticket", "tool_used": None, "answer_status": "ticket_confirmation_required"},
            ),
            (
                "请创建工单，订单号是 ORD10003（确认）",
                {"user_query": "请创建工单，订单号是 ORD10003", "confirm_ticket_creation": True},
                {"intent": "create_ticket", "tool_used": "order_tool.create_ticket", "answer_status": "answered"},
            ),
            (
                "我的银行卡被重复扣款了",
                {"user_query": "我的银行卡被重复扣款了"},
                {"intent": "human_handoff", "tool_used": None, "answer_status": "manual_review"},
            ),
            (
                "今天天气怎么样？",
                {"user_query": "今天天气怎么样？"},
                {"intent": "unknown", "tool_used": None, "answer_status": "unknown_request"},
            ),
        ]

        for name, payload, expected in scenarios:
            if payload is None:
                status_code, body, request_id, latency_ms = request_json("/health")
                passed = status_code == 200 and body.get("status") == "ok"
                result["scenarios"].append(
                    {
                        "name": name,
                        "http_status": status_code,
                        "request_id": request_id,
                        "intent": None,
                        "tool_used": None,
                        "answer_status": body.get("status"),
                        "passed": passed,
                        "latency_ms": latency_ms,
                        "failure_reason": None if passed else str(body),
                    }
                )
            else:
                result["scenarios"].append(run_scenario(name, payload, expected))

        result["passed"] = result["server_started"] and all(item["passed"] for item in result["scenarios"])
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        write_outputs(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
