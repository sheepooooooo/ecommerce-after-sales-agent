"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

from scripts.stability_test import (
    check_log_lines,
    classify_concurrent_result,
    validate_agent_response,
)


# 验证响应校验能识别缺 request_id、重复 request_id、5xx 和非法 body。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_validate_agent_response_detects_common_failures() -> None:
    seen: set[str] = set()
    valid = {
        "http_status": 200,
        "request_id": "req-1",
        "body": {"answer_status": "answered", "tool_trace": [], "api_latency_ms": 1},
    }
    assert validate_agent_response(valid, seen) == (True, None)
    assert validate_agent_response(valid, seen)[1] == "duplicate_request_id"
    missing_request = {"http_status": 200, "request_id": "", "body": {"answer_status": "answered", "tool_trace": [], "api_latency_ms": 1}}
    assert validate_agent_response(missing_request, seen)[1] == "missing_request_id"
    server_error = {"http_status": 500, "request_id": "req-2", "body": {}}
    assert validate_agent_response(server_error, seen)[1] == "unexpected_5xx:500"
    invalid_body = {"http_status": 200, "request_id": "req-3", "body": None}
    assert validate_agent_response(invalid_body, seen)[1] == "invalid_json_body"


# 验证并发统计能区分 200、503 busy 和异常。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_classify_concurrent_result_counts_success_busy_and_failure() -> None:
    seen: set[str] = set()
    success = {"http_status": 200, "request_id": "req-1", "body": {"request_id": "req-1"}}
    busy = {"http_status": 503, "request_id": "req-2", "body": {"error": {"code": "agent_busy"}}}
    failure = {"http_status": None, "request_id": None, "body": None, "error": "connection failed"}

    assert classify_concurrent_result(success, seen) == "success"
    assert classify_concurrent_result(busy, seen) == "busy"
    assert classify_concurrent_result(failure, seen) == "failure"


# 验证日志检查能发现未脱敏订单号和敏感字段。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_check_log_lines_detects_sensitive_content() -> None:
    log_text = (
        '{"timestamp":"t","level":"INFO","event":"e","request_id":"r",'
        '"endpoint":"/agent/run","http_status":200,"masked_order_id":"ORD10003"}\n'
        '{"timestamp":"t","level":"INFO","event":"e","request_id":"r2",'
        '"endpoint":"/agent/run","http_status":200,"message":"DEEPSEEK_API_KEY"}\n'
    )

    result = check_log_lines(log_text)

    assert result["passed"] is False
    assert result["issues"]


# 验证合法结构化日志可以通过检查。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_check_log_lines_accepts_safe_json_logs() -> None:
    log_text = (
        '{"timestamp":"t","level":"INFO","event":"e","request_id":"r",'
        '"endpoint":"/agent/run","http_status":200,"masked_order_id":"ORD***"}\n'
    )

    result = check_log_lines(log_text)

    assert result["passed"] is True
    assert result["parsed_line_count"] == 1
