"""
Local learning demo for the after-sales Agent.

The print output here is only for local learning and demonstration, not formal
logging. Real API/service logs live under the observability modules.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from app.agent.after_sales_agent_service import run_after_sales_agent
from app.services.trace_store import list_trace_events
from scripts.init_demo_data import initialize_database


def retry_success_policy_stub(query: str) -> dict:
    return {
        "success": True,
        "query": query,
        "answer_status": "answered",
        "answer": "模拟：第一次 LLM 超时后，重试成功并返回政策回答。",
        "retrieval_mode": "stub",
        "retrieved_chunks": [],
        "citations": [{"chunk_id": "stub", "source_file": "stub.md", "section_title": "stub"}],
        "has_relevant_policy": True,
        "generation": None,
        "grounding_verification": {"passed": True},
        "message": "retry success demo",
        "error": None,
        "debug": {
            "llm_called": True,
            "retry_count": 1,
            "retry_trace_events": [
                {
                    "step": "policy_qa_tool.ask_policy_question",
                    "action_type": "retry_attempt",
                    "status": "error",
                    "retry_count": 1,
                    "error_category": "llm_timeout",
                    "latency_ms": 1,
                },
                {
                    "step": "policy_qa_tool.ask_policy_question",
                    "action_type": "retry_success",
                    "status": "success",
                    "retry_count": 1,
                    "latency_ms": 1,
                },
            ],
        },
    }


def retry_exhausted_policy_stub(query: str) -> dict:
    return {
        "success": True,
        "query": query,
        "answer_status": "degraded",
        "answer": "当前政策回答服务暂时不可用，以下仅返回已检索到的模拟政策依据摘要。",
        "retrieval_mode": "stub",
        "retrieved_chunks": [],
        "citations": [{"chunk_id": "stub", "source_file": "stub.md", "section_title": "stub"}],
        "has_relevant_policy": True,
        "generation": None,
        "grounding_verification": {"passed": False, "reason": "degraded"},
        "message": "retry exhausted demo",
        "error": "timeout",
        "debug": {
            "llm_called": True,
            "retry_count": 2,
            "degraded": True,
            "fallback_action": "return_retrieved_policy_evidence",
            "error_category": "llm_timeout",
            "retry_trace_events": [
                {
                    "step": "policy_qa_tool.ask_policy_question",
                    "action_type": "retry_attempt",
                    "status": "error",
                    "retry_count": 1,
                    "error_category": "llm_timeout",
                    "latency_ms": 1,
                },
                {
                    "step": "policy_qa_tool.ask_policy_question",
                    "action_type": "retry_exhausted",
                    "status": "error",
                    "retry_count": 2,
                    "error_category": "llm_timeout",
                    "latency_ms": 1,
                },
                {
                    "step": "policy_qa_tool.ask_policy_question",
                    "action_type": "fallback",
                    "status": "degraded",
                    "retry_count": 2,
                    "error_category": "llm_timeout",
                    "fallback_action": "return_retrieved_policy_evidence",
                    "degraded": True,
                    "latency_ms": 0,
                },
            ],
        },
    }


def show_result(title: str, result: dict) -> None:
    print(f"\n{title}")
    print(
        json.dumps(
            {
                "session_id": result["session_id"],
                "intent": result["intent"],
                "tool_used": result["tool_used"],
                "answer_status": result["answer_status"],
                "confirmation_required": result["confirmation_required"],
                "data": result["data"],
                "idempotency_key": result.get("debug", {}).get("idempotency_key"),
                "retry_count": result.get("retry_count"),
                "degraded": result.get("degraded"),
                "error_category": result.get("error_category"),
                "fallback_action": result.get("fallback_action"),
                "workflow_summary": result.get("workflow_summary"),
                "answer": result["answer"],
                "error": result["error"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def run_single_turn_demo() -> None:
    scenarios = [
        ("耳机买了以后一般保修多长时间？", False),
        ("ORD10003 现在是什么状态？", False),
        ("ORD10004 可以直接退款吗？", False),
        ("我想退款。", False),
        ("我的银行卡被重复扣款了。", False),
        ("今天天气怎么样？", False),
    ]

    for index, (query, confirm) in enumerate(scenarios, start=1):
        result = run_after_sales_agent(
            query,
            confirm_ticket_creation=confirm,
            request_id=f"single-demo-{index}",
        )
        show_result(f"单轮场景 {index}: {query}", result)


def run_multi_turn_demo() -> None:
    create_first = run_after_sales_agent(
        "帮我给 ORD10003 创建售后工单",
        request_id="multi-confirm-1",
    )
    show_result("多轮确认 1/2: 创建工单但未确认", create_first)

    create_confirm = run_after_sales_agent(
        "确认",
        request_id="multi-confirm-2",
        session_id=create_first["session_id"],
    )
    show_result("多轮确认 2/2: 同一 session 确认创建", create_confirm)

    repeat_confirm = run_after_sales_agent(
        "确认",
        request_id="multi-confirm-3",
        session_id=create_first["session_id"],
    )
    show_result("多轮确认 3/3: 重复确认返回同一 ticket_id", repeat_confirm)

    fixed_key = "demo-fixed-idempotency-key"
    idem_first = run_after_sales_agent(
        "请帮我创建工单，订单号 ORD10006",
        confirm_ticket_creation=True,
        request_id="idem-demo-1",
        idempotency_key=fixed_key,
    )
    show_result("幂等 Demo 1/2: 首次带固定 idempotency_key 提交", idem_first)

    idem_second = run_after_sales_agent(
        "请帮我创建工单，订单号 ORD10006",
        confirm_ticket_creation=True,
        request_id="idem-demo-2",
        idempotency_key=fixed_key,
    )
    show_result("幂等 Demo 2/2: 相同 idempotency_key 重复提交", idem_second)

    cancel_first = run_after_sales_agent(
        "帮我给 ORD10004 创建售后工单",
        request_id="multi-cancel-1",
    )
    show_result("多轮取消 1/2: 创建工单但未确认", cancel_first)

    cancel_second = run_after_sales_agent(
        "取消",
        request_id="multi-cancel-2",
        session_id=cancel_first["session_id"],
    )
    show_result("多轮取消 2/2: 同一 session 取消", cancel_second)

    no_pending = run_after_sales_agent(
        "确认",
        request_id="multi-no-pending",
        session_id="demo-empty-session",
    )
    show_result("无待办确认: 不创建工单", no_pending)

    session_a = run_after_sales_agent(
        "帮我给 ORD10005 创建售后工单",
        request_id="multi-isolation-a1",
        session_id="demo-session-a",
    )
    show_result("会话隔离 A: 保存 ORD10005 待确认", session_a)

    session_b = run_after_sales_agent(
        "确认",
        request_id="multi-isolation-b1",
        session_id="demo-session-b",
    )
    show_result("会话隔离 B: 不能确认 A 的待办", session_b)


def run_workflow_resume_demo() -> None:
    refund_first = run_after_sales_agent(
        "帮我退款",
        request_id="resume-demo-refund-1",
    )
    show_result("多轮信息补全 1/10: 退款缺订单号", refund_first)
    refund_second = run_after_sales_agent(
        "ORD10003",
        request_id="resume-demo-refund-2",
        session_id=refund_first["session_id"],
    )
    show_result("多轮信息补全 2/10: 补订单号后恢复退款判断", refund_second)

    lookup_first = run_after_sales_agent(
        "查订单",
        request_id="resume-demo-lookup-1",
    )
    show_result("多轮信息补全 3/10: 查询缺订单号", lookup_first)
    lookup_second = run_after_sales_agent(
        "ORD10003",
        request_id="resume-demo-lookup-2",
        session_id=lookup_first["session_id"],
    )
    show_result("多轮信息补全 4/10: 补订单号后恢复查询", lookup_second)

    ticket_first = run_after_sales_agent(
        "创建工单",
        request_id="resume-demo-ticket-1",
    )
    show_result("多轮信息补全 5/10: 工单缺订单号", ticket_first)
    ticket_second = run_after_sales_agent(
        "ORD10003",
        request_id="resume-demo-ticket-2",
        session_id=ticket_first["session_id"],
    )
    show_result("多轮信息补全 6/10: 补订单号后进入确认", ticket_second)
    ticket_confirm = run_after_sales_agent(
        "确认",
        request_id="resume-demo-ticket-3",
        session_id=ticket_first["session_id"],
    )
    show_result("多轮信息补全 7/10: 确认后创建模拟工单", ticket_confirm)

    workflow_first = run_after_sales_agent(
        "订单能退吗，不行就建工单",
        request_id="resume-demo-workflow-1",
    )
    show_result("多轮信息补全 8/10: 复合任务缺订单号", workflow_first)
    workflow_second = run_after_sales_agent(
        "ORD10003",
        request_id="resume-demo-workflow-2",
        session_id=workflow_first["session_id"],
    )
    show_result("多轮信息补全 9/10: 补订单号后继续复合流程", workflow_second)

    cancel_first = run_after_sales_agent(
        "帮我退款",
        request_id="resume-demo-cancel-1",
    )
    cancelled = run_after_sales_agent(
        "取消",
        request_id="resume-demo-cancel-2",
        session_id=cancel_first["session_id"],
    )
    show_result("多轮信息补全 10/10: 待补订单号时取消", cancelled)

    interrupt_first = run_after_sales_agent(
        "帮我退款",
        request_id="resume-demo-interrupt-1",
    )
    interrupted = run_after_sales_agent(
        "那我问一下保修多久",
        request_id="resume-demo-interrupt-2",
        session_id=interrupt_first["session_id"],
    )
    show_result("多轮信息补全: 新政策问题中断旧 pending", interrupted)
    print("\nTrace 查询: resume-demo-workflow-2")
    print(json.dumps(list_trace_events("resume-demo-workflow-2"), ensure_ascii=False, indent=2))


def run_controlled_workflow_demo() -> None:
    eligible = run_after_sales_agent(
        "ORD10004 能退款吗？如果不能，帮我创建售后工单。",
        request_id="workflow-demo-eligible",
    )
    show_result("受控复合流程 1/6: 可退款时不创建工单", eligible)

    ineligible = run_after_sales_agent(
        "ORD10003 能退款吗？如果不能，帮我创建售后工单。",
        request_id="workflow-demo-ineligible",
    )
    show_result("受控复合流程 2/6: 不可直接退款时等待确认", ineligible)

    confirmed = run_after_sales_agent(
        "确认",
        request_id="workflow-demo-confirm",
        session_id=ineligible["session_id"],
    )
    show_result("受控复合流程 3/6: 同一 session 确认后创建模拟工单", confirmed)

    cancel_first = run_after_sales_agent(
        "ORD10003 能退款吗？如果不能，帮我创建售后工单。",
        request_id="workflow-demo-cancel-first",
    )
    cancelled = run_after_sales_agent(
        "取消",
        request_id="workflow-demo-cancel-second",
        session_id=cancel_first["session_id"],
    )
    show_result("受控复合流程 4/6: 同一 session 取消后不写工单", cancelled)

    missing_order = run_after_sales_agent(
        "能退款吗？如果不能，帮我创建售后工单。",
        request_id="workflow-demo-missing-order",
    )
    show_result("受控复合流程 5/6: 缺订单号先追问", missing_order)

    high_risk = run_after_sales_agent(
        "ORD10003 能退款吗？如果不能帮我创建售后工单，我银行卡重复扣款了。",
        request_id="workflow-demo-high-risk",
    )
    show_result("受控复合流程 6/6: 高风险问题优先人工兜底", high_risk)

    print("\nTrace 查询: workflow-demo-ineligible")
    print(json.dumps(list_trace_events("workflow-demo-ineligible"), ensure_ascii=False, indent=2))


def run_trace_demo() -> None:
    order_lookup = run_after_sales_agent(
        "ORD10003 现在是什么状态？",
        request_id="trace-demo-order",
    )
    show_result("Trace Demo: 订单查询请求", order_lookup)
    print("\nTrace 查询: trace-demo-order")
    print(json.dumps(list_trace_events("trace-demo-order"), ensure_ascii=False, indent=2))

    refund_check = run_after_sales_agent(
        "ORD10004 可以直接退款吗？",
        request_id="trace-demo-refund",
    )
    show_result("Trace Demo: 退款资格判断请求", refund_check)
    print("\nTrace 查询: trace-demo-refund")
    print(json.dumps(list_trace_events("trace-demo-refund"), ensure_ascii=False, indent=2))


def run_retry_degradation_demo() -> None:
    retry_success = run_after_sales_agent(
        "耳机保修多久？",
        request_id="retry-demo-success",
        policy_qa_callable=retry_success_policy_stub,
    )
    show_result("重试 Demo: 首次失败后重试成功", retry_success)
    print("\nTrace 查询: retry-demo-success")
    print(json.dumps(list_trace_events("retry-demo-success"), ensure_ascii=False, indent=2))

    retry_exhausted = run_after_sales_agent(
        "退货后优惠券会退回来吗？",
        request_id="retry-demo-degraded",
        policy_qa_callable=retry_exhausted_policy_stub,
    )
    show_result("降级 Demo: 重试耗尽后安全降级", retry_exhausted)
    print("\nTrace 查询: retry-demo-degraded")
    print(json.dumps(list_trace_events("retry-demo-degraded"), ensure_ascii=False, indent=2))


def main() -> None:
    initialize_database()
    print("售后 Agent Demo：以下 print 仅用于本地学习演示，不是正式日志。")
    run_single_turn_demo()
    run_multi_turn_demo()
    run_workflow_resume_demo()
    run_controlled_workflow_demo()
    run_trace_demo()
    run_retry_degradation_demo()


if __name__ == "__main__":
    main()
