"""
检查外部 RAG 项目是否具备真实计算 Hit@K / Recall@K / MRR 的条件。

本脚本只读取指定目录并生成检查报告，不修改 RAG 项目代码，不伪造评测指标。
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "docs" / "resume_evidence"
REPORT_MD = OUTPUT_DIR / "RAG_METRICS_READINESS_REPORT.md"
REPORT_JSON = OUTPUT_DIR / "RAG_METRICS_READINESS_REPORT.json"

EVAL_FILE_PATTERNS = ["*eval*.jsonl", "*questions*.jsonl", "*dataset*.jsonl"]
RESULT_FILE_PATTERNS = ["*result*.json", "*result*.jsonl", "*summary*.json", "*report*.md"]
SCRIPT_FILE_PATTERNS = ["evaluate*.py", "*eval*.py", "*retrieval*.py"]
LOG_FILE_PATTERNS = ["*.log", "*latency*.json", "*trace*.jsonl"]
SOURCE_FIELDS = {
    "source",
    "source_file",
    "file",
    "filename",
    "doc_id",
    "document_id",
    "page",
    "page_number",
    "chunk_id",
    "chunk",
    "expected_source",
    "expected_sources",
    "relevant_doc_ids",
    "golden_chunk_ids",
}


def find_files(root: Path, patterns: list[str]) -> list[str]:
    found: list[str] = []
    for pattern in patterns:
        for path in root.rglob(pattern):
            if path.is_file():
                found.append(str(path.relative_to(root)))
    return sorted(set(found))


def inspect_jsonl_annotations(path: Path, max_lines: int = 50) -> dict[str, Any]:
    checked_lines = 0
    annotated_lines = 0
    discovered_fields: set[str] = set()

    try:
        with path.open("r", encoding="utf-8") as input_file:
            for line in input_file:
                if checked_lines >= max_lines:
                    break
                if not line.strip():
                    continue
                checked_lines += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    fields = set(row.keys())
                    matched_fields = fields & SOURCE_FIELDS
                    if matched_fields:
                        annotated_lines += 1
                        discovered_fields.update(matched_fields)
    except UnicodeDecodeError:
        return {
            "checked_lines": checked_lines,
            "annotated_lines": annotated_lines,
            "discovered_fields": [],
            "read_error": "utf-8 decode failed",
        }

    return {
        "checked_lines": checked_lines,
        "annotated_lines": annotated_lines,
        "discovered_fields": sorted(discovered_fields),
        "read_error": None,
    }


def inspect_eval_annotations(root: Path, eval_files: list[str]) -> dict[str, Any]:
    details = []
    total_checked = 0
    total_annotated = 0
    all_fields: set[str] = set()

    for relative_path in eval_files:
        if not relative_path.endswith(".jsonl"):
            continue
        detail = inspect_jsonl_annotations(root / relative_path)
        details.append({"file": relative_path, **detail})
        total_checked += int(detail["checked_lines"])
        total_annotated += int(detail["annotated_lines"])
        all_fields.update(detail["discovered_fields"])

    return {
        "total_checked_lines": total_checked,
        "total_annotated_lines": total_annotated,
        "discovered_annotation_fields": sorted(all_fields),
        "details": details,
    }


def infer_next_steps(eval_scripts: list[str], result_files: list[str]) -> list[str]:
    steps: list[str] = []
    for script in eval_scripts:
        if re.search(r"evaluate|eval", Path(script).name, flags=re.IGNORECASE):
            steps.append(f"可优先检查并运行：python {script}")
    if not steps and result_files:
        steps.append("已发现结果文件，可先确认其中是否包含 query、retrieved chunk、gold source 对齐信息。")
    if not steps:
        steps.append("未发现明确评测脚本；需先补充人工标注评测集和检索评测脚本。")
    return steps


def build_readiness_report(rag_project_path: Path) -> dict[str, Any]:
    exists = rag_project_path.exists() and rag_project_path.is_dir()
    if not exists:
        return {
            "checked_at": datetime.now().replace(microsecond=0).isoformat(),
            "rag_project_path": str(rag_project_path),
            "path_exists": False,
            "can_compute_hit_recall_mrr": False,
            "missing_items": ["RAG 项目路径不存在或不是目录。"],
            "next_steps": ["确认 --rag-project-path 指向真实 RAG 项目根目录。"],
        }

    eval_files = find_files(rag_project_path, EVAL_FILE_PATTERNS)
    result_files = find_files(rag_project_path, RESULT_FILE_PATTERNS)
    eval_scripts = find_files(rag_project_path, SCRIPT_FILE_PATTERNS)
    log_files = find_files(rag_project_path, LOG_FILE_PATTERNS)
    annotation_report = inspect_eval_annotations(rag_project_path, eval_files)

    has_eval_jsonl = bool(eval_files)
    has_source_annotations = annotation_report["total_annotated_lines"] > 0
    has_results = bool(result_files)
    has_eval_scripts = bool(eval_scripts)
    has_logs = bool(log_files)
    can_compute = has_eval_jsonl and has_source_annotations and has_results and has_eval_scripts

    missing_items: list[str] = []
    if not has_eval_jsonl:
        missing_items.append("未发现评测题 JSONL。")
    if not has_source_annotations:
        missing_items.append("未确认评测题包含 source/file/page/chunk 等人工标注。")
    if not has_results:
        missing_items.append("未发现检索结果或实验结果文件。")
    if not has_eval_scripts:
        missing_items.append("未发现明确评测脚本。")
    if not has_logs:
        missing_items.append("未发现日志或耗时记录；这不阻止计算 Hit@K/MRR，但不利于补充延迟指标。")

    return {
        "checked_at": datetime.now().replace(microsecond=0).isoformat(),
        "rag_project_path": str(rag_project_path),
        "path_exists": True,
        "eval_files": eval_files,
        "annotation_report": annotation_report,
        "retrieval_result_or_experiment_files": result_files,
        "evaluation_scripts": eval_scripts,
        "log_or_latency_files": log_files,
        "can_compute_hit_recall_mrr": can_compute,
        "missing_items": missing_items,
        "next_steps": infer_next_steps(eval_scripts, result_files),
        "calculation_boundary": (
            "只有存在人工标注的相关 source/file/page/chunk，并能与检索结果逐题对齐时，"
            "才能真实计算 Hit@K、Recall@K、MRR。"
        ),
    }


def write_outputs(report: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# RAG 指标可计算性检查报告",
        "",
        f"- 检查时间：{report['checked_at']}",
        f"- RAG 项目路径：{report['rag_project_path']}",
        f"- 路径是否存在：{report['path_exists']}",
        f"- 当前能否真实计算 Hit@K / Recall@K / MRR：{report['can_compute_hit_recall_mrr']}",
        "",
        "## 已发现材料",
        "",
        f"- 评测题 JSONL：{report.get('eval_files', [])}",
        f"- 人工标注字段：{report.get('annotation_report', {}).get('discovered_annotation_fields', [])}",
        f"- 检索结果或实验结果：{report.get('retrieval_result_or_experiment_files', [])}",
        f"- 评测脚本：{report.get('evaluation_scripts', [])}",
        f"- 日志或耗时记录：{report.get('log_or_latency_files', [])}",
        "",
        "## 缺少什么",
        "",
    ]
    missing_items = report.get("missing_items", [])
    if missing_items:
        lines.extend(f"- {item}" for item in missing_items)
    else:
        lines.append("- 未发现阻断项；仍需人工确认标注含义和评测脚本口径。")

    lines.extend(
        [
            "",
            "## 下一步建议",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report.get("next_steps", []))
    lines.extend(
        [
            "",
            "## 指标边界",
            "",
            "- 没有人工标注时，不能声称 Recall@K 或 MRR，因为无法判断某条检索结果是否真相关。",
            "- 只有题目、人工标注答案来源和检索结果能够逐题对齐时，才能计算 Hit@K、Recall@K、MRR。",
            "- 本脚本不修改 RAG 项目代码，也不计算虚假结果。",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="检查 RAG 指标可计算性。")
    parser.add_argument("--rag-project-path", required=True, help="外部 RAG 项目根目录。")
    args = parser.parse_args()

    report = build_readiness_report(Path(args.rag_project_path))
    write_outputs(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
