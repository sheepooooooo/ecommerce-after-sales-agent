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

from app.retrieval.embedding_service import embed_single_text
from app.tools.policy_retrieval_tool import retrieve_policy


EVAL_DATASET_PATH = PROJECT_ROOT_FOR_IMPORTS / "eval" / "policy_retrieval_eval_questions.jsonl"
EVAL_RESULTS_DIRECTORY = PROJECT_ROOT_FOR_IMPORTS / "eval_results"
RETRIEVAL_MODES = ["bm25", "dense", "hybrid"]


def load_eval_questions() -> list[dict[str, Any]]:
    """
    读取政策检索评测集。

    参数：
        无。

    返回：
        list[dict[str, Any]]：评测问题列表。

    用途：
        三种检索策略使用同一评测集，保证对比可复现。
    """
    question_list: list[dict[str, Any]] = []
    with EVAL_DATASET_PATH.open("r", encoding="utf-8") as input_file:
        for line_text in input_file:
            if line_text.strip():
                question_list.append(json.loads(line_text))
    return question_list


def warmup_embedding_model() -> float:
    """
    预热 Embedding 模型并记录首次加载耗时。

    参数：
        无。

    返回：
        float：首次加载和一次编码耗时，单位毫秒。

    用途：
        延迟对比不应把模型首次加载时间算进平均检索耗时。
    """
    start_time = time.perf_counter()
    embed_single_text("模型预热：订单发货后不想要了怎么办")
    end_time = time.perf_counter()
    return (end_time - start_time) * 1000


def analyze_failure_reason(result: dict[str, Any]) -> str:
    """
    为 badcase 生成初步失败原因。

    参数：
        result：单条评测结果。

    返回：
        str：简短中文分析。

    用途：
        帮助后续理解 BM25、Dense 或 Hybrid 的失败模式。
    """
    if result["expected_source_file"] is None and result["has_relevant_policy"]:
        return "无关问题被误判为存在相关政策，可能需要进一步校准相关性阈值。"
    if result["expected_source_file"] is not None and not result["hit_at_3"]:
        return "Top3 未召回期望政策，可能是用户口语表达与政策关键词或向量语义仍有差距。"
    if result["expected_source_file"] is not None and not result["hit_at_1"]:
        return "Top3 命中但 Top1 未命中，说明排序仍有优化空间。"
    return "非失败样本。"


def evaluate_one_question(question: dict[str, Any], retrieval_mode: str) -> dict[str, Any]:
    """
    使用指定模式评测单个问题。

    参数：
        question：评测问题。
        retrieval_mode：检索模式。

    返回：
        dict[str, Any]：评测明细。

    用途：
        记录 Top1、Top3、命中情况、无答案判断和检索耗时。
    """
    start_time = time.perf_counter()
    retrieval_result = retrieve_policy(
        query=question["query"],
        top_k=3,
        retrieval_mode=retrieval_mode,
    )
    end_time = time.perf_counter()

    retrieved_chunks = retrieval_result["retrieved_chunks"]
    top3_source_files = [
        retrieved_chunk["source_file"] for retrieved_chunk in retrieved_chunks[:3]
    ]
    top1_source_file = top3_source_files[0] if top3_source_files else None
    top1_score = None
    if retrieved_chunks:
        top1_score = (
            retrieved_chunks[0].get("bm25_score")
            or retrieved_chunks[0].get("dense_score")
            or retrieved_chunks[0].get("rrf_score")
        )

    expected_source_file = question["expected_source_file"]
    expect_relevant_policy = bool(question["expect_relevant_policy"])
    hit_at_1 = expect_relevant_policy and top1_source_file == expected_source_file
    hit_at_3 = expect_relevant_policy and expected_source_file in top3_source_files
    no_answer_correct = (
        not expect_relevant_policy
        and not retrieval_result["has_relevant_policy"]
    )

    result = {
        "id": question["id"],
        "query": question["query"],
        "retrieval_mode": retrieval_mode,
        "expected_source_file": expected_source_file,
        "top1_source_file": top1_source_file,
        "top3_source_files": top3_source_files,
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "no_answer_correct": no_answer_correct,
        "has_relevant_policy": retrieval_result["has_relevant_policy"],
        "relevance_reason": retrieval_result["relevance_reason"],
        "top1_score": top1_score,
        "latency_ms": round((end_time - start_time) * 1000, 4),
    }
    result["failure_reason"] = analyze_failure_reason(result)
    return result


def calculate_summary(
    evaluation_results: list[dict[str, Any]],
    embedding_model_warmup_ms: float,
) -> dict[str, Any]:
    """
    汇总单种模式的评测指标。

    参数：
        evaluation_results：该模式下全部问题的评测结果。
        embedding_model_warmup_ms：模型首次加载耗时。

    返回：
        dict[str, Any]：汇总指标。

    用途：
        对比 Hit@1、Hit@3、无关识别准确率和平均检索延迟。
    """
    relevant_results = [
        result for result in evaluation_results
        if result["expected_source_file"] is not None
    ]
    irrelevant_results = [
        result for result in evaluation_results
        if result["expected_source_file"] is None
    ]
    relevant_question_count = len(relevant_results)
    irrelevant_question_count = len(irrelevant_results)
    average_latency_ms = (
        sum(result["latency_ms"] for result in evaluation_results) / len(evaluation_results)
        if evaluation_results
        else 0.0
    )

    return {
        "total_questions": len(evaluation_results),
        "relevant_question_count": relevant_question_count,
        "irrelevant_question_count": irrelevant_question_count,
        "hit_at_1": (
            sum(1 for result in relevant_results if result["hit_at_1"]) / relevant_question_count
            if relevant_question_count
            else 0.0
        ),
        "hit_at_3": (
            sum(1 for result in relevant_results if result["hit_at_3"]) / relevant_question_count
            if relevant_question_count
            else 0.0
        ),
        "no_answer_accuracy": (
            sum(1 for result in irrelevant_results if result["no_answer_correct"]) / irrelevant_question_count
            if irrelevant_question_count
            else 0.0
        ),
        "average_retrieval_latency_ms": round(average_latency_ms, 4),
        "embedding_model_warmup_ms": round(embedding_model_warmup_ms, 4),
        "latency_note": "average_retrieval_latency_ms 不包含首次模型加载预热时间。",
    }


def write_mode_outputs(
    retrieval_mode: str,
    evaluation_results: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    """
    写入单种模式的评测结果、summary 和 badcase。

    参数：
        retrieval_mode：检索模式。
        evaluation_results：评测明细。
        summary：汇总指标。

    返回：
        None。

    用途：
        保留每种策略的独立结果，方便后续横向对比。
    """
    EVAL_RESULTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    results_path = EVAL_RESULTS_DIRECTORY / f"policy_retrieval_{retrieval_mode}_results.jsonl"
    summary_path = EVAL_RESULTS_DIRECTORY / f"policy_retrieval_{retrieval_mode}_summary.json"
    badcase_path = EVAL_RESULTS_DIRECTORY / f"policy_retrieval_{retrieval_mode}_badcases.md"

    with results_path.open("w", encoding="utf-8") as output_file:
        for result in evaluation_results:
            output_file.write(json.dumps(result, ensure_ascii=False) + "\n")

    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    badcase_lines = [
        f"# {retrieval_mode} 检索 Badcase",
        "",
        "以下记录包含 Top1 未命中、Top3 未命中或无关问题误召回的样本。",
        "",
    ]
    badcase_count = 0
    for result in evaluation_results:
        is_badcase = False
        if result["expected_source_file"] is not None and not result["hit_at_1"]:
            is_badcase = True
        if result["expected_source_file"] is None and not result["no_answer_correct"]:
            is_badcase = True
        if not is_badcase:
            continue
        badcase_count += 1
        badcase_lines.extend(
            [
                f"## {result['id']}",
                "",
                f"- 问题：{result['query']}",
                f"- 期望来源：{result['expected_source_file']}",
                f"- 实际 Top1：{result['top1_source_file']}",
                f"- Top3 来源：{result['top3_source_files']}",
                f"- Hit@1：{result['hit_at_1']}",
                f"- Hit@3：{result['hit_at_3']}",
                f"- 失败原因初步分析：{result['failure_reason']}",
                "",
            ]
        )
    if badcase_count == 0:
        badcase_lines.append("当前模式未发现 badcase。")
    badcase_path.write_text("\n".join(badcase_lines), encoding="utf-8")


def write_comparison_outputs(comparison_summary: dict[str, Any]) -> None:
    """
    写入三种检索策略的对比结果。

    参数：
        comparison_summary：包含三种模式 summary 的字典。

    返回：
        None。

    用途：
        生成统一对比 JSON 和 Markdown 报告。
    """
    comparison_path = EVAL_RESULTS_DIRECTORY / "policy_retrieval_comparison.json"
    report_path = EVAL_RESULTS_DIRECTORY / "policy_retrieval_comparison_report.md"
    comparison_path.write_text(
        json.dumps(comparison_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_lines = [
        "# 政策检索对比实验报告",
        "",
        "## 指标说明",
        "",
        "- Hit@1：相关问题中，Top1 来源文件是否命中预期政策。",
        "- Hit@3：相关问题中，Top3 来源文件是否包含预期政策。",
        "- 无关问题识别准确率：无关问题是否正确返回无相关政策。",
        "- 平均检索耗时：模型预热后的平均检索耗时，不包含首次模型加载时间。",
        "",
        "## 对比结果",
        "",
        "| 模式 | Hit@1 | Hit@3 | 无关识别 | 平均耗时 ms |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for retrieval_mode, summary in comparison_summary["mode_summaries"].items():
        report_lines.append(
            f"| {retrieval_mode} | {summary['hit_at_1']:.4f} | "
            f"{summary['hit_at_3']:.4f} | {summary['no_answer_accuracy']:.4f} | "
            f"{summary['average_retrieval_latency_ms']:.4f} |"
        )

    report_lines.extend(
        [
            "",
            "## 结论与边界",
            "",
            "本报告依据真实评测结果生成，不预设 Hybrid 必然最好。",
            "当前政策库规模较小，BM25 对精确术语已经较强；Dense 有助于口语化表达召回，",
            "但向量检索会为无关问题返回最相近 chunk，因此必须结合相关性阈值。",
        ]
    )
    report_path.write_text("\n".join(report_lines), encoding="utf-8")


def evaluate_policy_retrieval() -> dict[str, Any]:
    """
    执行三种检索策略的完整对比评测。

    参数：
        无。

    返回：
        dict[str, Any]：三种模式的对比 summary。

    用途：
        作为命令行脚本和后续回归验收的统一入口。
    """
    question_list = load_eval_questions()
    embedding_model_warmup_ms = warmup_embedding_model()
    mode_summaries: dict[str, Any] = {}

    for retrieval_mode in RETRIEVAL_MODES:
        evaluation_results = [
            evaluate_one_question(question, retrieval_mode)
            for question in question_list
        ]
        summary = calculate_summary(evaluation_results, embedding_model_warmup_ms)
        write_mode_outputs(retrieval_mode, evaluation_results, summary)
        mode_summaries[retrieval_mode] = summary

    comparison_summary = {
        "retrieval_modes": RETRIEVAL_MODES,
        "embedding_model_warmup_ms": round(embedding_model_warmup_ms, 4),
        "mode_summaries": mode_summaries,
    }
    write_comparison_outputs(comparison_summary)
    return comparison_summary


if __name__ == "__main__":
    summary_result = evaluate_policy_retrieval()
    print("政策检索对比评测完成")
    print(json.dumps(summary_result, ensure_ascii=False, indent=2))
