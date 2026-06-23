"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

from typing import Any

from fastapi.testclient import TestClient

import app.api_server as api_server
from app.api.dependencies import get_policy_qa_callable
from app.api_server import app
from scripts.init_demo_data import initialize_database


def policy_stub(query: str) -> dict[str, Any]:
    return {
        "success": True,
        "query": query,
        "answer_status": "answered",
        "answer": "stub",
        "retrieval_mode": "stub",
        "retrieved_chunks": [],
        "citations": [],
        "has_relevant_policy": True,
        "generation": None,
        "grounding_verification": {"passed": True},
        "message": "ok",
        "error": None,
        "debug": {"llm_called": False},
    }


def make_client(raise_server_exceptions: bool = True) -> TestClient:
    app.dependency_overrides[get_policy_qa_callable] = lambda: policy_stub
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def assert_validation_error(response: Any) -> None:
    body = response.json()
    assert response.status_code == 422
    assert body["success"] is False
    assert body["error"]["code"] == "validation_error"
    assert body["request_id"] == response.headers["X-Request-ID"]


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_invalid_empty_query_returns_structured_422() -> None:
    with make_client() as client:
        response = client.post("/agent/run", json={"user_query": "   "})

    assert_validation_error(response)


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_invalid_long_query_returns_structured_422() -> None:
    with make_client() as client:
        response = client.post("/agent/run", json={"user_query": "x" * 1001})

    assert_validation_error(response)


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_invalid_confirm_type_returns_structured_422() -> None:
    with make_client() as client:
        response = client.post(
            "/agent/run",
            json={"user_query": "请创建工单", "confirm_ticket_creation": "true"},
        )

    assert_validation_error(response)


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_unknown_field_returns_structured_422() -> None:
    with make_client() as client:
        response = client.post(
            "/agent/run",
            json={"user_query": "ORD10003 现在是什么状态？", "extra": "not allowed"},
        )

    assert_validation_error(response)


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_internal_error_returns_safe_500(monkeypatch: Any) -> None:
    initialize_database()

    def broken_agent(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("secret traceback path C:/private/project and token sk-xxx")

    monkeypatch.setattr(api_server, "run_after_sales_agent", broken_agent)

    with make_client(raise_server_exceptions=False) as client:
        response = client.post("/agent/run", json={"user_query": "ORD10003 现在是什么状态？"})

    body = response.json()
    assert response.status_code == 500
    assert body["success"] is False
    assert body["error"]["code"] == "internal_server_error"
    assert "traceback" not in response.text.lower()
    assert "C:/private" not in response.text
    assert "sk-xxx" not in response.text
