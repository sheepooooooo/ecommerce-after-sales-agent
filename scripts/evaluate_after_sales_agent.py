"""
【文件作用】
本文件是项目中的 Python 模块，用于支撑当前目录对应的 Agent、RAG、Tool、API 或工程化能力。

【在项目中的位置】
它会被项目内的服务、脚本或测试按需导入。请结合文件名和所在目录理解具体调用关系。

【主要输入与输出】
输入和输出取决于具体函数。本注释只解释阅读路径，不改变业务逻辑、数据库、LLM 或 API 行为。
"""

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from app.agent.after_sales_agent_service import run_after_sales_agent
from scripts.init_demo_data import initialize_database


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_FILE = PROJECT_ROOT / "eval" / "after_sales_agent_eval_questions.jsonl"
RESULTS_DIR = PROJECT_ROOT / "eval_results"


def policy_qa_stub(query: str) -> dict[str, Any]:
    return {
        "success": True,
        "query": query,
        "answer_status": "answered",
        "answer": "这是政策问答 stub 返回，用于离线评测路由，不评价真实 LLM 文案。",
        "retrieval_mode": "stub",
        "retrieved_chunks": [],
        "citations": [{"chunk_id": "stub-1", "source_file": "stub.md", "section_title": "stub"}],
        "has_relevant_policy": True,
        "generation": None,
        "grounding_verification": {"passed": True, "reason": "stub"},
        "message": "stub",
        "error": None,
        "debug": {"llm_called": False},
    }


def load_questions() -> list[dict[str, Any]]:
    questions = []
    with EVAL_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                questions.append(json.loads(line))
    return questions


def is_match(actual: Any, expected: Any) -> bool:
    if expected is None:
        return actual is None
    return actual == expected


def calculate_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    intent_correct = sum(item["checks"]["intent"] for item in results)
    tool_correct = sum(item["checks"]["tool_used"] for item in results)
    order_correct = sum(item["checks"]["order_id"] for item in results)
    missing_cases = [item for item in results if item["expected"].get("answer_status") == "missing_order_id"]
    ticket_cases = [item for item in results if item["expected"].get("intent") == "create_ticket"]
    successful = sum(item["passed"] for item in results)

    return {
        "total_questions": total,
        "intent_accuracy": intent_correct / total if total else 0,
        "tool_selection_accuracy": tool_correct / total if total else 0,
        "order_id_extraction_accuracy": order_correct / total if total else 0,
        "missing_order_id_handling_accuracy": (
            sum(item["checks"]["answer_status"] for item in missing_cases) / len(missing_cases)
            if missing_cases
            else 0
        ),
        "ticket_confirmation_safety_accuracy": (
            sum(item["checks"]["answer_status"] for item in ticket_cases) / len(ticket_cases)
            if ticket_cases
            else 0
        ),
        "success_rate": successful / total if total else 0,
    }


def write_outputs(results: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results_path = RESULTS_DIR / "after_sales_agent_eval_results.jsonl"
    with results_path.open("w", encoding="utf-8") as file:
        for item in results:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")

    (RESULTS_DIR / "after_sales_agent_eval_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_lines = [
        "# 售后 Agent 离线评测报告",
        "",
        f"- total_questions: {summary['total_questions']}",
        f"- intent_accuracy: {summary['intent_accuracy']:.4f}",
        f"- tool_selection_accuracy: {summary['tool_selection_accuracy']:.4f}",
        f"- order_id_extraction_accuracy: {summary['order_id_extraction_accuracy']:.4f}",
        f"- missing_order_id_handling_accuracy: {summary['missing_order_id_handling_accuracy']:.4f}",
        f"- ticket_confirmation_safety_accuracy: {summary['ticket_confirmation_safety_accuracy']:.4f}",
        f"- success_rate: {summary['success_rate']:.4f}",
    ]
    (RESULTS_DIR / "after_sales_agent_eval_report.md").write_text(
        "\n".join(report_lines) + "\n",
        encoding="utf-8",
    )

    badcases = [item for item in results if not item["passed"]]
    badcase_lines = ["# 售后 Agent Badcases", ""]
    if not badcases:
        badcase_lines.append("暂无 badcase。")
    for item in badcases:
        badcase_lines.append(f"- {item['id']}: {item['query']}")
        badcase_lines.append(f"  - expected: {item['expected']}")
        badcase_lines.append(f"  - actual: {item['actual']}")
    (RESULTS_DIR / "after_sales_agent_badcases.md").write_text(
        "\n".join(badcase_lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    initialize_database()
    questions = load_questions()
    results = []

    for item in questions:
        result = run_after_sales_agent(
            item["query"],
            confirm_ticket_creation=item.get("confirm_ticket_creation", False),
            request_id=item["id"],
            policy_qa_callable=policy_qa_stub,
        )
        actual_order_id = result["debug"].get("all_detected_order_ids", [None])
        actual_first_order_id = actual_order_id[0] if actual_order_id else None
        expected = item["expected"]
        checks = {
            "intent": is_match(result["intent"], expected.get("intent")),
            "tool_used": is_match(result["tool_used"], expected.get("tool_used")),
            "order_id": is_match(actual_first_order_id, expected.get("order_id")),
            "answer_status": is_match(result["answer_status"], expected.get("answer_status")),
        }
        results.append(
            {
                "id": item["id"],
                "query": item["query"],
                "expected": expected,
                "actual": {
                    "intent": result["intent"],
                    "tool_used": result["tool_used"],
                    "order_id": actual_first_order_id,
                    "answer_status": result["answer_status"],
                },
                "checks": checks,
                "passed": all(checks.values()),
            }
        )

    summary = calculate_summary(results)
    write_outputs(results, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
