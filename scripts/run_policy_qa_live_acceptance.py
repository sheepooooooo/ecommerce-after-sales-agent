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


from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from app.config import get_llm_config
from app.tools.policy_qa_tool import ask_policy_question


EVAL_RESULTS_DIR = PROJECT_ROOT_FOR_IMPORTS / "eval_results"
JSON_RESULT_PATH = EVAL_RESULTS_DIR / "policy_qa_live_acceptance.json"
REPORT_PATH = EVAL_RESULTS_DIR / "policy_qa_live_acceptance_report.md"


@dataclass(frozen=True)
class LiveAcceptanceCase:
    case_id: str
    title: str
    query: str
    expected_statuses: tuple[str, ...]
    expected_llm_called: bool
    required_source_file: str | None = None
    require_legal_citation: bool = False
    require_order_tool_boundary: bool = False
    require_no_deterministic_refund_conclusion: bool = False


LIVE_ACCEPTANCE_CASES = [
    LiveAcceptanceCase(
        case_id="Q1",
        title="耳机保修多久",
        query="耳机买了以后一般保修多长时间？",
        expected_statuses=("answered",),
        expected_llm_called=True,
        required_source_file="invoice_warranty_policy.md",
        require_legal_citation=True,
    ),
    LiveAcceptanceCase(
        case_id="Q2",
        title="支付成功但订单待付款",
        query="我付款成功了，为什么订单还是待付款？",
        expected_statuses=("answered", "manual_review"),
        expected_llm_called=True,
        required_source_file="payment_policy.md",
        require_legal_citation=True,
    ),
    LiveAcceptanceCase(
        case_id="Q3",
        title="已发货后不想要",
        query="商品已经发货，但我临时不想要了怎么办？",
        expected_statuses=("answered",),
        expected_llm_called=True,
        required_source_file="cancellation_policy.md",
        require_legal_citation=True,
    ),
    LiveAcceptanceCase(
        case_id="Q4",
        title="退货后优惠券",
        query="退货以后优惠券会退回来吗？",
        expected_statuses=("answered", "manual_review"),
        expected_llm_called=True,
        required_source_file="coupon_policy.md",
        require_legal_citation=True,
    ),
    LiveAcceptanceCase(
        case_id="Q5",
        title="具体订单退款资格边界",
        query="ORD10004 可以直接退款吗？",
        expected_statuses=("manual_review",),
        expected_llm_called=False,
        require_order_tool_boundary=True,
        require_no_deterministic_refund_conclusion=True,
    ),
    LiveAcceptanceCase(
        case_id="Q6",
        title="无关天气问题",
        query="今天天气怎么样？",
        expected_statuses=("no_relevant_policy",),
        expected_llm_called=False,
    ),
]


def classify_error(error_message: str | None) -> str | None:
    """
    将错误文本归类，避免把底层异常全文当成验收主结论。
    """
    if not error_message:
        return None
    normalized_message = error_message.lower()
    if "deepseek_api_key" in normalized_message:
        return "missing_api_key"
    if "timeout" in normalized_message or "超时" in error_message:
        return "timeout"
    if "json" in normalized_message or "解析" in error_message:
        return "json_parse_error"
    if "api" in normalized_message or "状态" in error_message:
        return "api_error"
    if "connection" in normalized_message or "连接" in error_message or "网络" in error_message:
        return "connection_error"
    return "unknown_error"


def extract_missing_information(response: dict[str, Any]) -> list[str]:
    generation = response.get("generation")
    if isinstance(generation, dict):
        missing_information = generation.get("missing_information", [])
        if isinstance(missing_information, list):
            return [str(item) for item in missing_information]
    return []


def extract_model_cited_chunk_ids(response: dict[str, Any]) -> list[str]:
    generation = response.get("generation")
    if isinstance(generation, dict):
        cited_chunk_ids = generation.get("cited_chunk_ids", [])
        if isinstance(cited_chunk_ids, list):
            return [str(chunk_id) for chunk_id in cited_chunk_ids]
    return []


def summarize_retrieved_chunks(response: dict[str, Any]) -> list[dict[str, Any]]:
    retrieved_chunks = response.get("retrieved_chunks", [])
    if not isinstance(retrieved_chunks, list):
        return []

    chunk_summary_list: list[dict[str, Any]] = []
    for retrieved_chunk in retrieved_chunks:
        if not isinstance(retrieved_chunk, dict):
            continue
        chunk_summary_list.append(
            {
                "rank": retrieved_chunk.get("rank"),
                "chunk_id": retrieved_chunk.get("chunk_id"),
                "source_file": retrieved_chunk.get("source_file"),
                "section_title": retrieved_chunk.get("section_title"),
                "bm25_score": retrieved_chunk.get("bm25_score"),
                "dense_score": retrieved_chunk.get("dense_score"),
                "rrf_score": retrieved_chunk.get("rrf_score"),
            }
        )
    return chunk_summary_list


def contains_deterministic_refund_conclusion(answer: str) -> bool:
    """
    检查是否直接给出了“可以退款/不可以退款”式确定结论。
    """
    deterministic_phrases = [
        "可以直接退款",
        "不可以直接退款",
        "可以退款。",
        "不可以退款。",
        "可以退款，",
        "不可以退款，",
    ]
    return any(phrase in answer for phrase in deterministic_phrases)


def looks_like_order_tool_boundary(answer_status: str, answer: str) -> bool:
    if answer_status == "manual_review":
        return True
    return "订单" in answer and any(
        keyword in answer
        for keyword in ["订单查询", "退款资格规则 Tool", "退款规则 Tool", "退款资格规则", "规则 Tool"]
    )


def evaluate_case(case: LiveAcceptanceCase, response: dict[str, Any], elapsed_ms: float) -> dict[str, Any]:
    debug_info = response.get("debug", {})
    if not isinstance(debug_info, dict):
        debug_info = {}

    citations = response.get("citations", [])
    if not isinstance(citations, list):
        citations = []
    citation_chunk_ids = [str(citation.get("chunk_id", "")) for citation in citations if isinstance(citation, dict)]
    citation_source_files = [str(citation.get("source_file", "")) for citation in citations if isinstance(citation, dict)]
    retrieved_chunk_summary_list = summarize_retrieved_chunks(response)

    grounding_verification = response.get("grounding_verification", {})
    if not isinstance(grounding_verification, dict):
        grounding_verification = {}

    generation = response.get("generation")
    needs_human_review = generation.get("needs_human_review") if isinstance(generation, dict) else None
    answer_status = str(response.get("answer_status", ""))
    answer = str(response.get("answer", ""))
    llm_called = bool(debug_info.get("llm_called", False))
    grounding_passed = bool(grounding_verification.get("passed", False))
    failure_reasons: list[str] = []

    if answer_status not in case.expected_statuses:
        failure_reasons.append(
            f"answer_status={answer_status}，预期为 {', '.join(case.expected_statuses)}。"
        )
    if llm_called != case.expected_llm_called:
        failure_reasons.append(f"llm_called={llm_called}，预期为 {case.expected_llm_called}。")
    if case.require_legal_citation and not citation_chunk_ids:
        failure_reasons.append("缺少合法引用。")
    if case.require_legal_citation and not grounding_passed:
        failure_reasons.append("引用合法性校验未通过。")
    if case.required_source_file and case.required_source_file not in citation_source_files:
        failure_reasons.append(f"引用来源未包含 {case.required_source_file}。")
    if case.require_order_tool_boundary and not looks_like_order_tool_boundary(answer_status, answer):
        failure_reasons.append("未明确提示需要订单查询和退款资格规则 Tool。")
    if case.require_no_deterministic_refund_conclusion and contains_deterministic_refund_conclusion(answer):
        failure_reasons.append("具体订单问题输出了确定退款结论。")

    total_latency_ms = debug_info.get("total_latency_ms")
    if total_latency_ms is None:
        total_latency_ms = round(elapsed_ms, 4)

    return {
        "case_id": case.case_id,
        "title": case.title,
        "query": case.query,
        "answer_status": answer_status,
        "success": bool(response.get("success", False)),
        "llm_called": llm_called,
        "retrieval_mode": response.get("retrieval_mode"),
        "has_relevant_policy": bool(response.get("has_relevant_policy", False)),
        "retrieved_topk_chunks": retrieved_chunk_summary_list,
        "retrieved_topk_chunk_ids": [
            str(chunk["chunk_id"]) for chunk in retrieved_chunk_summary_list if chunk.get("chunk_id")
        ],
        "retrieved_topk_source_files": [
            str(chunk["source_file"]) for chunk in retrieved_chunk_summary_list if chunk.get("source_file")
        ],
        "retrieved_topk_section_titles": [
            str(chunk["section_title"]) for chunk in retrieved_chunk_summary_list if chunk.get("section_title")
        ],
        "model_cited_chunk_ids": extract_model_cited_chunk_ids(response),
        "citation_chunk_ids": citation_chunk_ids,
        "citation_source_files": citation_source_files,
        "grounding_verification_passed": grounding_passed,
        "needs_human_review": needs_human_review,
        "missing_information": extract_missing_information(response),
        "total_latency_ms": total_latency_ms,
        "retrieval_latency_ms": debug_info.get("retrieval_latency_ms"),
        "generation_latency_ms": debug_info.get("generation_latency_ms", 0.0),
        "error_type": classify_error(response.get("error")),
        "error": response.get("error"),
        "passed": not failure_reasons,
        "failure_reasons": failure_reasons,
        "answer_preview": answer[:180],
    }


def run_live_acceptance() -> dict[str, Any]:
    llm_config = get_llm_config(require_api_key=False)
    case_results: list[dict[str, Any]] = []

    for case in LIVE_ACCEPTANCE_CASES:
        case_start_time = time.perf_counter()
        try:
            response = ask_policy_question(
                query=case.query,
                top_k=3,
                retrieval_mode="bm25",
            )
        except Exception as error:
            response = {
                "success": False,
                "query": case.query,
                "answer_status": "generation_error",
                "answer": "验收脚本调用政策问答 Tool 失败。",
                "retrieval_mode": "bm25",
                "retrieved_chunks": [],
                "citations": [],
                "has_relevant_policy": False,
                "generation": None,
                "grounding_verification": {"passed": False, "reason": "脚本捕获异常。"},
                "message": "脚本捕获异常。",
                "error": str(error),
                "debug": {"llm_called": False},
            }
        elapsed_ms = (time.perf_counter() - case_start_time) * 1000
        case_results.append(evaluate_case(case, response, elapsed_ms))

    passed_count = sum(1 for result in case_results if result["passed"])
    return {
        "acceptance_time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": llm_config["model"],
        "llm_enable_thinking": llm_config["enable_thinking"],
        "retrieval_mode": "bm25",
        "total_cases": len(case_results),
        "passed_cases": passed_count,
        "all_passed": passed_count == len(case_results),
        "results": case_results,
        "boundary_note": (
            "本验收仅验证真实 DeepSeek 调用下的智选商城模拟政策问答链路，"
            "不代表真实平台政策、法律意见或真实售后操作。"
        ),
    }


def write_json_result(summary: dict[str, Any]) -> None:
    EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    JSON_RESULT_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def format_list(items: list[str]) -> str:
    return "、".join(items) if items else "无"


def format_retrieved_chunks(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "无"
    formatted_chunks: list[str] = []
    for chunk in chunks:
        score_parts: list[str] = []
        if chunk.get("bm25_score") is not None:
            score_parts.append(f"BM25={chunk['bm25_score']}")
        if chunk.get("dense_score") is not None:
            score_parts.append(f"Dense={chunk['dense_score']}")
        if chunk.get("rrf_score") is not None:
            score_parts.append(f"RRF={chunk['rrf_score']}")
        score_text = f"，{'，'.join(score_parts)}" if score_parts else ""
        formatted_chunks.append(
            f"{chunk.get('rank')}. {chunk.get('chunk_id')} / "
            f"{chunk.get('source_file')} / {chunk.get('section_title')}{score_text}"
        )
    return "<br>".join(formatted_chunks)


def write_markdown_report(summary: dict[str, Any]) -> None:
    report_lines = [
        "# 政策问答真实模型验收报告",
        "",
        f"- 验收时间：{summary['acceptance_time']}",
        f"- 模型名：{summary['model']}",
        f"- 是否启用 thinking：{summary['llm_enable_thinking']}",
        f"- 通过数量 / 总数量：{summary['passed_cases']} / {summary['total_cases']}",
        f"- 检索模式：{summary['retrieval_mode']}",
        "",
        "## 逐题结果",
        "",
    ]

    for result in summary["results"]:
        failure_text = "无" if result["passed"] else format_list(result["failure_reasons"])
        report_lines.extend(
            [
                f"### {result['case_id']} {result['title']}",
                "",
                f"- 问题：{result['query']}",
                f"- 实际状态：{result['answer_status']}",
                f"- 是否通过：{result['passed']}",
                f"- 是否调用 LLM：{result['llm_called']}",
                f"- 是否存在相关政策：{result['has_relevant_policy']}",
                f"- 本次检索 TopK：{format_retrieved_chunks(result['retrieved_topk_chunks'])}",
                f"- 模型最终 cited_chunk_ids：{format_list(result['model_cited_chunk_ids'])}",
                f"- 模型最终引用 source_file：{format_list(result['citation_source_files'])}",
                f"- 合法引用 chunk_id：{format_list(result['citation_chunk_ids'])}",
                f"- 合法引用来源：{format_list(result['citation_source_files'])}",
                f"- 引用校验是否通过：{result['grounding_verification_passed']}",
                f"- 是否建议人工处理：{result['needs_human_review']}",
                f"- 缺失信息：{format_list(result['missing_information'])}",
                f"- 总耗时：{result['total_latency_ms']} ms",
                f"- 检索耗时：{result['retrieval_latency_ms']} ms",
                f"- 生成耗时：{result['generation_latency_ms']} ms",
                f"- 错误类型：{result['error_type'] or '无'}",
                f"- 失败项与初步原因：{failure_text}",
                "",
            ]
        )

    failed_results = [result for result in summary["results"] if not result["passed"]]
    report_lines.extend(
        [
            "## 失败项汇总",
            "",
        ]
    )
    if not failed_results:
        report_lines.append("全部固定验收问题通过。")
    else:
        for result in failed_results:
            report_lines.append(
                f"- {result['case_id']} {result['title']}：{format_list(result['failure_reasons'])}"
            )

    report_lines.extend(
        [
            "",
            "## 项目边界说明",
            "",
            "- 本报告仅记录智选商城模拟政策问答链路的工程验收结果。",
            "- 本脚本会真实调用 DeepSeek，但不会写入或打印 API Key。",
            "- 本脚本不执行真实退款、真实取消订单、真实物流修改或真实工单创建。",
            "- 引用合法性只表示引用来自本次检索证据，不等于答案绝对正确。",
            "- 具体订单退款资格仍应由订单查询 Tool 和退款资格规则 Tool 判断。",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(report_lines), encoding="utf-8")


if __name__ == "__main__":
    print("开始执行政策问答真实模型验收。此脚本仅用于本地学习演示，不作为正式日志方案。")
    acceptance_summary = run_live_acceptance()
    write_json_result(acceptance_summary)
    write_markdown_report(acceptance_summary)
    print(f"验收完成：{acceptance_summary['passed_cases']} / {acceptance_summary['total_cases']} 通过。")
    print(f"JSON 结果：{JSON_RESULT_PATH}")
    print(f"Markdown 报告：{REPORT_PATH}")
    if not acceptance_summary["all_passed"]:
        print("存在未通过项，请查看报告中的失败原因。")

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
