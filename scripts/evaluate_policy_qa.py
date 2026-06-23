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
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from app.tools.policy_qa_tool import ask_policy_question


EVAL_DATASET_PATH = PROJECT_ROOT_FOR_IMPORTS / "eval" / "policy_qa_eval_questions.jsonl"
EVAL_RESULTS_DIRECTORY = PROJECT_ROOT_FOR_IMPORTS / "eval_results"


def load_eval_questions() -> list[dict[str, Any]]:
    """
    读取政策问答评测集。

    参数：
        无。

    返回：
        list[dict[str, Any]]：评测问题列表。

    用途：
        将问答评测问题与政策知识库分开，避免数据泄漏。
    """
    questions: list[dict[str, Any]] = []
    with EVAL_DATASET_PATH.open("r", encoding="utf-8") as input_file:
        for line_text in input_file:
            if line_text.strip():
                questions.append(json.loads(line_text))
    return questions


def evaluate_one_question(question: dict[str, Any]) -> dict[str, Any]:
    """
    评测单个政策问答问题。

    参数：
        question：评测集中的单个问题。

    返回：
        dict[str, Any]：评测明细。

    用途：
        记录状态、引用、来源命中和延迟。
    """
    start_time = time.perf_counter()
    response = ask_policy_question(question["query"], retrieval_mode="bm25", top_k=3)
    total_latency_ms = (time.perf_counter() - start_time) * 1000
    citation_sources = [
        citation["source_file"] for citation in response.get("citations", [])
    ]
    expected_source_file = question["expected_source_file"]
    expected_source_hit = (
        expected_source_file is None
        or expected_source_file in citation_sources
        or expected_source_file in [
            chunk.get("source_file") for chunk in response.get("retrieved_chunks", [])
        ]
    )
    grounding = response.get("grounding_verification") or {}
    debug = response.get("debug") or {}

    return {
        "id": question["id"],
        "query": question["query"],
        "expect_answer_status": question["expect_answer_status"],
        "actual_answer_status": response.get("answer_status"),
        "expected_source_file": expected_source_file,
        "actual_citation_sources": citation_sources,
        "retrieval_mode": response.get("retrieval_mode"),
        "citation_valid": bool(grounding.get("passed")),
        "expected_source_hit": expected_source_hit,
        "success": bool(response.get("success")),
        "expect_human_review": bool(question["expect_human_review"]),
        "actual_human_review": bool((response.get("generation") or {}).get("needs_human_review")) or response.get("answer_status") == "manual_review",
        "error": response.get("error"),
        "manual_checkpoints": question["manual_checkpoints"],
        "total_latency_ms": round(total_latency_ms, 4),
        "retrieval_latency_ms": float(debug.get("retrieval_latency_ms", 0.0) or 0.0),
        "generation_latency_ms": float(debug.get("generation_latency_ms", 0.0) or 0.0),
    }


def calculate_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    汇总政策问答评测指标。

    参数：
        results：评测明细列表。

    返回：
        dict[str, Any]：汇总指标。

    用途：
        给出自动化指标，但不替代人工质量审核。
    """
    total = len(results)
    answered_or_manual = [
        result for result in results
        if result["actual_answer_status"] in {"answered", "manual_review"}
    ]
    no_relevant_expected = [
        result for result in results
        if result["expect_answer_status"] == "no_relevant_policy"
    ]
    manual_expected = [
        result for result in results
        if result["expect_answer_status"] == "manual_review" or result["expect_human_review"]
    ]

    return {
        "total_questions": total,
        "success_rate": sum(1 for result in results if result["success"]) / total if total else 0.0,
        "answer_status_match_rate": sum(1 for result in results if result["actual_answer_status"] == result["expect_answer_status"]) / total if total else 0.0,
        "citation_valid_rate": (
            sum(1 for result in answered_or_manual if result["citation_valid"]) / len(answered_or_manual)
            if answered_or_manual
            else 0.0
        ),
        "expected_source_hit_rate": sum(1 for result in results if result["expected_source_hit"]) / total if total else 0.0,
        "no_relevant_policy_accuracy": (
            sum(1 for result in no_relevant_expected if result["actual_answer_status"] == "no_relevant_policy") / len(no_relevant_expected)
            if no_relevant_expected
            else 0.0
        ),
        "manual_review_match_rate": (
            sum(1 for result in manual_expected if result["actual_human_review"]) / len(manual_expected)
            if manual_expected
            else 0.0
        ),
        "average_total_latency_ms": sum(result["total_latency_ms"] for result in results) / total if total else 0.0,
        "average_retrieval_latency_ms": sum(result["retrieval_latency_ms"] for result in results) / total if total else 0.0,
        "average_generation_latency_ms": sum(result["generation_latency_ms"] for result in results) / total if total else 0.0,
    }


def write_outputs(results: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    """
    写入 QA 评测结果文件。

    参数：
        results：评测明细。
        summary：汇总指标。

    返回：
        None。

    用途：
        保存 jsonl、summary、report 和 badcases。
    """
    EVAL_RESULTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (EVAL_RESULTS_DIRECTORY / "policy_qa_results.jsonl").write_text(
        "\n".join(json.dumps(result, ensure_ascii=False) for result in results) + "\n",
        encoding="utf-8",
    )
    (EVAL_RESULTS_DIRECTORY / "policy_qa_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_lines = [
        "# 政策问答评测报告",
        "",
        "## 自动指标",
        "",
        json.dumps(summary, ensure_ascii=False, indent=2),
        "",
        "## 人工检查边界",
        "",
        "回答是否真正完整、语气是否合适、是否正确覆盖政策例外情况，仍需要人工根据 manual_checkpoints 进行审核；本阶段自动指标不能替代人工质量评估。",
    ]
    (EVAL_RESULTS_DIRECTORY / "policy_qa_report.md").write_text("\n".join(report_lines), encoding="utf-8")

    badcase_lines = ["# 政策问答 Badcase", ""]
    for result in results:
        is_badcase = (
            result["actual_answer_status"] != result["expect_answer_status"]
            or not result["expected_source_hit"]
            or (result["actual_answer_status"] == "answered" and not result["citation_valid"])
            or result["error"]
        )
        if not is_badcase:
            continue
        badcase_lines.extend(
            [
                f"## {result['id']}",
                "",
                f"- 问题：{result['query']}",
                f"- 期望状态：{result['expect_answer_status']}",
                f"- 实际状态：{result['actual_answer_status']}",
                f"- 期望来源：{result['expected_source_file']}",
                f"- 实际引用来源：{result['actual_citation_sources']}",
                f"- 检索模式：{result['retrieval_mode']}",
                f"- 引用是否有效：{result['citation_valid']}",
                f"- 错误信息或初步分析：{result['error'] or '需人工查看回答内容与 checkpoints。'}",
                "",
            ]
        )
    if len(badcase_lines) == 2:
        badcase_lines.append("当前自动指标未发现 badcase。")
    (EVAL_RESULTS_DIRECTORY / "policy_qa_badcases.md").write_text("\n".join(badcase_lines), encoding="utf-8")


def evaluate_policy_qa() -> dict[str, Any]:
    """
    执行政策问答评测。

    参数：
        无。

    返回：
        dict[str, Any]：汇总指标。

    用途：
        作为命令行评测入口。
    """
    questions = load_eval_questions()
    results = [evaluate_one_question(question) for question in questions]
    summary = calculate_summary(results)
    write_outputs(results, summary)
    return summary


if __name__ == "__main__":
    summary_result = evaluate_policy_qa()
    print("政策问答评测完成")
    print(json.dumps(summary_result, ensure_ascii=False, indent=2))
