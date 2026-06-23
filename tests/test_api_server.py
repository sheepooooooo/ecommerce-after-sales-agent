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

from app.api.dependencies import get_policy_qa_callable
from app.api_server import app
from app.tools.order_tool import list_tickets
from scripts.init_demo_data import initialize_database


def policy_stub(query: str) -> dict[str, Any]:
    return {
        "success": True,
        "query": query,
        "answer_status": "answered",
        "answer": "API policy stub answer",
        "retrieval_mode": "stub",
        "retrieved_chunks": [],
        "citations": [{"chunk_id": "stub", "source_file": "stub.md", "section_title": "stub"}],
        "has_relevant_policy": True,
        "generation": None,
        "grounding_verification": {"passed": True},
        "message": "ok",
        "error": None,
        "debug": {"llm_called": False},
    }


def make_client() -> TestClient:
    app.dependency_overrides[get_policy_qa_callable] = lambda: policy_stub
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_health_returns_ok() -> None:
    with make_client() as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Request-ID"]


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_agent_order_lookup_api_response() -> None:
    initialize_database()
    with make_client() as client:
        response = client.post("/agent/run", json={"user_query": "ORD10003 现在是什么状态？"})

    body = response.json()
    assert response.status_code == 200
    assert body["intent"] == "order_lookup"
    assert body["tool_used"] == "order_tool.get_order"
    assert body["answer_status"] == "answered"
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert body["api_latency_ms"] >= 0
    assert body["agent_latency_ms"] >= 0
    assert body["tool_trace"]
    assert body["tool_latency_summary"]["tool_count"] == 1


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_agent_refund_eligibility_api_response() -> None:
    initialize_database()
    with make_client() as client:
        response = client.post("/agent/run", json={"user_query": "ORD10004 可以退款吗？"})

    body = response.json()
    assert response.status_code == 200
    assert body["intent"] == "refund_eligibility"
    assert body["tool_used"] == "refund_eligibility_tool.check_refund_eligibility"
    assert body["data"]["eligible"] is True
    assert body["answer_status"] == "answered"


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_missing_order_id_does_not_call_refund_tool() -> None:
    initialize_database()
    with make_client() as client:
        response = client.post("/agent/run", json={"user_query": "我想退款"})

    body = response.json()
    assert body["answer_status"] == "missing_order_id"
    assert body["tool_used"] is None
    assert "refund_eligibility_tool.check_refund_eligibility" not in [
        item["step"] for item in body["tool_trace"]
    ]


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_ticket_confirmation_does_not_write_database() -> None:
    initialize_database()
    with make_client() as client:
        response = client.post("/agent/run", json={"user_query": "请创建工单，订单号是 ORD10003"})

    body = response.json()
    assert body["answer_status"] == "ticket_confirmation_required"
    assert body["tool_used"] is None
    assert list_tickets("ORD10003") == []


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_ticket_confirmed_writes_database() -> None:
    initialize_database()
    with make_client() as client:
        response = client.post(
            "/agent/run",
            json={
                "user_query": "请创建工单，订单号是 ORD10003",
                "confirm_ticket_creation": True,
            },
        )

    body = response.json()
    assert body["answer_status"] == "answered"
    assert body["tool_used"] == "order_tool.create_ticket"
    assert len(list_tickets("ORD10003")) == 1


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_policy_qa_uses_dependency_override() -> None:
    initialize_database()
    with make_client() as client:
        response = client.post("/agent/run", json={"user_query": "耳机保修多久？"})

    body = response.json()
    assert body["intent"] == "policy_qa"
    assert body["answer"] == "API policy stub answer"
    assert body["debug"]["policy_qa"]["llm_called"] is False


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_body_request_id_and_header_request_id() -> None:
    initialize_database()
    with make_client() as client:
        response = client.post(
            "/agent/run",
            headers={"X-Request-ID": "header-id"},
            json={"user_query": "ORD10003 现在是什么状态？", "request_id": "body-id"},
        )

    body = response.json()
    assert body["request_id"] == "body-id"
    assert response.headers["X-Request-ID"] == "body-id"
