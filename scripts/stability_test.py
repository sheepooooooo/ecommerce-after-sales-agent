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


import concurrent.futures
import json
import re
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

from scripts.bootstrap_runtime import bootstrap_runtime
from scripts.init_demo_data import initialize_database


HOST = "127.0.0.1"
PORT = 8012
BASE_URL = f"http://{HOST}:{PORT}"
RESULTS_DIR = PROJECT_ROOT / "eval_results"
SUMMARY_PATH = RESULTS_DIR / "stability_test_summary.json"
REPORT_PATH = RESULTS_DIR / "stability_test_report.md"
LOG_PATH = PROJECT_ROOT / "logs" / "agent_api.log"
SENSITIVE_PATTERNS = [
    "DEEPSEEK_API_KEY",
    "验证码",
    "密码",
    ".env",
    re.compile(r"\b\d{13,19}\b"),
    re.compile(r"\bORD\d{5}\b"),
]


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


def read_log_offset() -> int:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    if not LOG_PATH.exists():
        return 0
    return LOG_PATH.stat().st_size


def request_json(path: str, payload: dict[str, Any] | None = None, method: str = "GET") -> dict[str, Any]:
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
            raw_body = response.read().decode("utf-8")
            return {
                "http_status": response.status,
                "body": json.loads(raw_body),
                "request_id": response.headers.get("X-Request-ID", ""),
                "latency_ms": round((time.perf_counter() - start_time) * 1000, 2),
                "error": None,
            }
    except urllib.error.HTTPError as error:
        raw_body = error.read().decode("utf-8")
        return {
            "http_status": error.code,
            "body": json.loads(raw_body),
            "request_id": error.headers.get("X-Request-ID", ""),
            "latency_ms": round((time.perf_counter() - start_time) * 1000, 2),
            "error": None,
        }


def validate_agent_response(result: dict[str, Any], seen_request_ids: set[str]) -> tuple[bool, str | None]:
    """
    校验稳定性测试响应是否满足基础结构要求。
    """
    if result.get("error"):
        return False, str(result["error"])
    status = result.get("http_status")
    if isinstance(status, int) and status >= 500:
        return False, f"unexpected_5xx:{status}"
    body = result.get("body")
    if not isinstance(body, dict):
        return False, "invalid_json_body"
    request_id = result.get("request_id") or body.get("request_id")
    if not request_id:
        return False, "missing_request_id"
    if request_id in seen_request_ids:
        return False, "duplicate_request_id"
    seen_request_ids.add(request_id)
    if "answer_status" not in body:
        return False, "missing_answer_status"
    if "tool_trace" not in body:
        return False, "missing_tool_trace"
    if "api_latency_ms" not in body:
        return False, "missing_api_latency_ms"
    return True, None


def classify_concurrent_result(result: dict[str, Any], seen_request_ids: set[str]) -> str:
    """
    将并发结果分为 success、busy 或 failure。
    """
    if result.get("error"):
        return "failure"
    status = result.get("http_status")
    body = result.get("body", {})
    request_id = result.get("request_id") or body.get("request_id")
    if request_id in seen_request_ids:
        return "failure"
    if request_id:
        seen_request_ids.add(request_id)
    if status == 200:
        return "success"
    if status == 503 and body.get("error", {}).get("code") == "agent_busy":
        return "busy"
    return "failure"


def check_log_lines(log_text: str) -> dict[str, Any]:
    """
    检查本次追加日志是否可解析、字段是否齐全、是否包含敏感信息。
    """
    required_fields = {"timestamp", "level", "event", "request_id", "endpoint", "http_status"}
    issues: list[str] = []
    parsed_count = 0
    for line_number, line in enumerate(log_text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            issues.append(f"line_{line_number}_invalid_json")
            continue
        parsed_count += 1
        missing_fields = sorted(required_fields - set(item))
        if missing_fields:
            issues.append(f"line_{line_number}_missing_{','.join(missing_fields)}")
        line_text = json.dumps(item, ensure_ascii=False)
        for pattern in SENSITIVE_PATTERNS:
            if isinstance(pattern, str):
                if pattern in line_text:
                    issues.append(f"line_{line_number}_contains_sensitive_keyword_{pattern}")
            elif pattern.search(line_text):
                issues.append(f"line_{line_number}_contains_unmasked_sensitive_pattern")
    return {
        "passed": not issues and parsed_count > 0,
        "parsed_line_count": parsed_count,
        "issues": issues,
    }


def wait_for_health() -> bool:
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
            result = request_json("/health")
            if result["http_status"] == 200 and result["body"].get("status") == "ok":
                return True
        except Exception:
            time.sleep(0.5)
    return False


def safe_request(payload: dict[str, Any]) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    try:
        return request_json("/agent/run", payload=payload, method="POST")
    except Exception as error:
        return {"http_status": None, "body": None, "request_id": None, "latency_ms": 0, "error": str(error)}


def build_report(summary: dict[str, Any]) -> str:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    return "\n".join(
        [
            "# 稳定性测试报告",
            "",
            f"- 测试时间：{summary['tested_at']}",
            "- 测试环境说明：本地单进程 Uvicorn，端口 8012，不调用真实 LLM。",
            f"- 服务启动结果：{summary['service_startup_success']}",
            f"- 顺序调用：{summary['sequential_passed']} / {summary['sequential_total']}",
            f"- 并发调用总数：{summary['concurrent_total']}",
            f"- 并发成功数：{summary['concurrent_success_count']}",
            f"- 并发 busy 数：{summary['concurrent_busy_count']}",
            f"- 并发失败数：{summary['concurrent_failure_count']}",
            f"- 是否出现未预期 5xx：{summary['unexpected_error_count'] > 0}",
            f"- request_id 唯一数：{summary['unique_request_id_count']}",
            f"- 平均 API 耗时：{summary['average_api_latency_ms']} ms",
            f"- 最大 API 耗时：{summary['max_api_latency_ms']} ms",
            f"- 日志检查通过：{summary['log_check']['passed']}",
            f"- 日志问题：{summary['log_check']['issues']}",
            "",
            "## 已知边界",
            "",
            "- 这不是高并发压测，也不是生产级性能测试。",
            "- 进程内 Semaphore 不是分布式限流。",
            "- 当前不覆盖真实 LLM Policy QA。",
        ]
    ) + "\n"


def run_stability_test() -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    initialize_database()
    bootstrap_result = bootstrap_runtime()
    log_offset = read_log_offset()
    process: subprocess.Popen | None = None
    seen_request_ids: set[str] = set()
    sequential_results: list[dict[str, Any]] = []
    concurrent_results: list[dict[str, Any]] = []

    summary: dict[str, Any] = {
        "tested_at": datetime.now().replace(microsecond=0).isoformat(),
        "sequential_total": 0,
        "sequential_passed": 0,
        "concurrent_total": 0,
        "concurrent_success_count": 0,
        "concurrent_busy_count": 0,
        "concurrent_failure_count": 0,
        "unexpected_error_count": 0,
        "unique_request_id_count": 0,
        "average_api_latency_ms": 0,
        "max_api_latency_ms": 0,
        "service_startup_success": False,
        "bootstrap_result": bootstrap_result,
        "log_check": {"passed": False, "parsed_line_count": 0, "issues": ["not_run"]},
    }

    try:
        if is_port_in_use(HOST, PORT):
            raise RuntimeError(f"端口 {HOST}:{PORT} 已被占用，请停止已有服务后重试。")
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
        summary["service_startup_success"] = wait_for_health()
        if not summary["service_startup_success"]:
            raise RuntimeError("服务未能在限定时间内通过 /health 检查。")

        sequential_payloads = [
            {"user_query": "ORD10003 现在是什么状态？"},
            {"user_query": "ORD10004 可以退款吗？"},
            {"user_query": "我想退款"},
            {"user_query": "请创建工单，订单号是 ORD10003"},
            {"user_query": "我的银行卡被重复扣款了"},
            {"user_query": "今天天气怎么样？"},
        ] * 2

        for payload in sequential_payloads:
            result = safe_request(payload)
            passed, failure_reason = validate_agent_response(result, seen_request_ids)
            result["passed"] = passed
            result["failure_reason"] = failure_reason
            sequential_results.append(result)

        concurrent_payloads = [
            {"user_query": "ORD10003 现在是什么状态？"},
            {"user_query": "ORD10004 可以退款吗？"},
            {"user_query": "我想退款"},
            {"user_query": "我的银行卡被重复扣款了"},
            {"user_query": "今天天气怎么样？"},
        ]
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            concurrent_results = list(executor.map(safe_request, concurrent_payloads))

        concurrent_seen_ids: set[str] = set()
        classifications = [
            classify_concurrent_result(result, concurrent_seen_ids)
            for result in concurrent_results
        ]

        all_latencies = [
            result["latency_ms"]
            for result in [*sequential_results, *concurrent_results]
            if isinstance(result.get("latency_ms"), (int, float))
        ]
        unexpected_5xx = []
        for result in [*sequential_results, *concurrent_results]:
            status = result.get("http_status")
            body = result.get("body") if isinstance(result.get("body"), dict) else {}
            is_allowed_busy = status == 503 and body.get("error", {}).get("code") == "agent_busy"
            if isinstance(status, int) and status >= 500 and not is_allowed_busy:
                unexpected_5xx.append(result)

        summary.update(
            {
                "sequential_total": len(sequential_results),
                "sequential_passed": sum(1 for item in sequential_results if item["passed"]),
                "concurrent_total": len(concurrent_results),
                "concurrent_success_count": classifications.count("success"),
                "concurrent_busy_count": classifications.count("busy"),
                "concurrent_failure_count": classifications.count("failure"),
                "unexpected_error_count": len(unexpected_5xx),
                "unique_request_id_count": len(seen_request_ids | concurrent_seen_ids),
                "average_api_latency_ms": round(sum(all_latencies) / len(all_latencies), 2) if all_latencies else 0,
                "max_api_latency_ms": max(all_latencies) if all_latencies else 0,
            }
        )
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        appended_log = ""
        if LOG_PATH.exists():
            with LOG_PATH.open("r", encoding="utf-8") as log_file:
                log_file.seek(log_offset)
                appended_log = log_file.read()
        summary["log_check"] = check_log_lines(appended_log)
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        REPORT_PATH.write_text(build_report(summary), encoding="utf-8")

    return summary


if __name__ == "__main__":
    print(json.dumps(run_stability_test(), ensure_ascii=False, indent=2))

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
