"""
GitHub 发布前本地检查脚本。

本脚本只检查并生成报告，不删除文件、不读取 .env 内容、不执行 GitHub 操作。
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "docs" / "resume_evidence"
REPORT_MD = OUTPUT_DIR / "PRE_PUBLISH_CHECK_REPORT.md"
REPORT_JSON = OUTPUT_DIR / "PRE_PUBLISH_CHECK_REPORT.json"

SENSITIVE_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"DEEPSEEK_API_KEY[ \t]*=[ \t]*[^\s#]+"),
    re.compile(r"OPENAI_API_KEY[ \t]*=[ \t]*[^\s#]+"),
    re.compile(r"api[_-]?key[ \t]*[:=][ \t]*['\"][^'\"]{12,}['\"]", re.IGNORECASE),
]
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".example",
}
SKIP_DIR_NAMES = {".git", ".pytest_cache", "__pycache__"}
LARGE_FILE_THRESHOLD_BYTES = 20 * 1024 * 1024
PLACEHOLDER_SECRET_MARKERS = {
    "你的key",
    "your_key",
    "your-key",
    "your_api_key",
    "your-api-key",
    "<api_key>",
    "<your_api_key>",
    "placeholder",
}
REQUIRED_GITIGNORE_PATTERNS = {
    ".env",
    ".env.*",
    "!.env.example",
    "__pycache__/",
    ".pytest_cache/",
    "*.pyc",
    "logs/*.log",
    "data/orders.db",
    "data/indexes/",
    "eval_results/",
    ".venv/",
    "venv/",
}
LOCAL_ONLY_TARGETS = [
    {"path": ".env", "kind": "file", "description": "本地真实环境变量文件"},
    {"path": "logs/*.log", "kind": "glob", "description": "本地运行日志"},
    {"path": "data/orders.db", "kind": "file", "description": "本地 SQLite 模拟订单数据库"},
    {"path": "data/indexes", "kind": "directory", "description": "本地政策 chunk / FAISS 索引"},
    {"path": "eval_results", "kind": "directory", "description": "本地评测结果"},
    {"path": ".pytest_cache", "kind": "directory", "description": "pytest 本地缓存"},
    {"path": "__pycache__", "kind": "recursive_directory", "description": "Python 字节码缓存"},
    {"path": ".venv", "kind": "directory", "description": "本地虚拟环境"},
    {"path": "venv", "kind": "directory", "description": "本地虚拟环境"},
]


def read_gitignore_patterns() -> set[str]:
    gitignore_path = PROJECT_ROOT / ".gitignore"
    if not gitignore_path.exists():
        return set()
    return {
        line.strip()
        for line in gitignore_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


def iter_project_files() -> list[Path]:
    files: list[Path] = []
    for path in PROJECT_ROOT.rglob("*"):
        if any(part in SKIP_DIR_NAMES for part in path.relative_to(PROJECT_ROOT).parts):
            continue
        if path.is_file():
            files.append(path)
    return files


def get_repo_root() -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return Path(result.stdout.strip()).resolve()


def get_tracked_project_files() -> set[str]:
    repo_root = get_repo_root()
    if repo_root is None:
        return set()
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", str(PROJECT_ROOT)],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()

    tracked_files: set[str] = set()
    for raw_item in result.stdout.split(b"\0"):
        if not raw_item:
            continue
        repo_relative = raw_item.decode("utf-8", errors="replace")
        absolute_path = (repo_root / repo_relative).resolve()
        try:
            tracked_files.add(absolute_path.relative_to(PROJECT_ROOT).as_posix())
        except ValueError:
            continue
    return tracked_files


def is_ignored_by_git(path: Path) -> bool:
    if path.name == ".env.example":
        return False
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "--", str(path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


def is_submission_candidate(path: Path, tracked_files: set[str]) -> bool:
    relative_path = path.relative_to(PROJECT_ROOT).as_posix()
    if relative_path in tracked_files:
        return True
    return not is_ignored_by_git(path)


def tracked_under(path: Path, tracked_files: set[str]) -> list[str]:
    relative_path = path.relative_to(PROJECT_ROOT).as_posix()
    if path.is_file():
        return [relative_path] if relative_path in tracked_files else []
    prefix = relative_path.rstrip("/") + "/"
    return sorted(file_path for file_path in tracked_files if file_path.startswith(prefix))


def resolve_local_only_paths(target: dict[str, str]) -> list[Path]:
    kind = target["kind"]
    target_path = target["path"]
    if kind == "file":
        path = PROJECT_ROOT / target_path
        return [path] if path.exists() else []
    if kind == "directory":
        path = PROJECT_ROOT / target_path
        return [path] if path.exists() else []
    if kind == "glob":
        return sorted(PROJECT_ROOT.glob(target_path))
    if kind == "recursive_directory":
        return sorted(path for path in PROJECT_ROOT.rglob(target_path) if path.is_dir())
    return []


def classify_local_only_targets(tracked_files: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    local_only_safe: list[dict[str, Any]] = []
    tracked_risk: list[dict[str, Any]] = []
    ignore_rule_missing: list[dict[str, Any]] = []

    for target in LOCAL_ONLY_TARGETS:
        for path in resolve_local_only_paths(target):
            relative_path = path.relative_to(PROJECT_ROOT).as_posix()
            tracked_matches = tracked_under(path, tracked_files)
            ignored = is_ignored_by_git(path)
            item = {
                "path": relative_path,
                "description": target["description"],
                "ignored_by_gitignore": ignored,
                "tracked_files": tracked_matches,
            }
            if tracked_matches:
                tracked_risk.append(
                    {
                        **item,
                        "recommendation": "该本地风险文件或目录已有跟踪记录，发布前需从 Git 跟踪中移除但保留本地文件。",
                    }
                )
            elif not ignored:
                ignore_rule_missing.append(
                    {
                        **item,
                        "recommendation": "补充 .gitignore 规则，确保该本地产物不会被提交。",
                    }
                )
            else:
                local_only_safe.append(
                    {
                        **item,
                        "recommendation": "可保留在本地；已被 .gitignore 覆盖且未被 Git 跟踪。",
                    }
                )

    return local_only_safe, tracked_risk, ignore_rule_missing


def scan_for_sensitive_patterns(files: list[Path], tracked_files: set[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in files:
        relative_path = path.relative_to(PROJECT_ROOT).as_posix()
        if relative_path == ".env":
            continue
        if not is_submission_candidate(path, tracked_files):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".gitignore":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SENSITIVE_PATTERNS:
            matched_line = None
            for line in text.splitlines():
                if not pattern.search(line):
                    continue
                normalized_line = line.strip().lower()
                if any(marker in normalized_line for marker in PLACEHOLDER_SECRET_MARKERS):
                    continue
                matched_line = line
                break
            if matched_line is not None:
                findings.append(
                    {
                        "file": relative_path,
                        "pattern": pattern.pattern,
                        "recommendation": "人工检查该文件是否包含真实密钥；不要提交真实 API Key。",
                    }
                )
                break
    return findings


def build_report() -> dict[str, Any]:
    files = iter_project_files()
    gitignore_patterns = read_gitignore_patterns()
    tracked_files = get_tracked_project_files()
    local_only_safe, tracked_risk, ignore_rule_missing = classify_local_only_targets(tracked_files)
    env_exists = (PROJECT_ROOT / ".env").exists()
    log_files = sorted(str(path.relative_to(PROJECT_ROOT)) for path in (PROJECT_ROOT / "logs").glob("*.log")) if (PROJECT_ROOT / "logs").exists() else []
    pycache_dirs = sorted(
        str(path.relative_to(PROJECT_ROOT))
        for path in PROJECT_ROOT.rglob("__pycache__")
        if path.is_dir()
    )
    sensitive_findings = scan_for_sensitive_patterns(files, tracked_files)
    eval_sensitive_findings = [
        finding for finding in sensitive_findings
        if finding["file"].startswith("eval_results/")
    ]
    large_files = [
        {
            "file": str(path.relative_to(PROJECT_ROOT)),
            "size_bytes": path.stat().st_size,
        }
        for path in files
        if path.stat().st_size >= LARGE_FILE_THRESHOLD_BYTES and is_submission_candidate(path, tracked_files)
    ]
    large_files = sorted(large_files, key=lambda item: item["file"])

    key_gitignore_checks = {
        pattern: pattern in gitignore_patterns
        for pattern in sorted(REQUIRED_GITIGNORE_PATTERNS)
    }

    risk_items: list[dict[str, Any]] = []
    if tracked_risk:
        risk_items.append(
            {
                "level": "high",
                "item": "tracked_risk",
                "recommendation": "敏感或本地产物已被 Git 跟踪，发布前需从 Git 跟踪中移除。",
                "count": len(tracked_risk),
            }
        )
    if ignore_rule_missing:
        risk_items.append(
            {
                "level": "high",
                "item": "ignore_rule_missing",
                "recommendation": "关键本地产物未被 .gitignore 覆盖。",
                "count": len(ignore_rule_missing),
            }
        )
    if sensitive_findings:
        risk_items.append(
            {
                "level": "high",
                "item": "possible secret patterns",
                "recommendation": "逐项人工检查疑似密钥命中；本脚本不会打印密钥内容。",
                "count": len(sensitive_findings),
            }
        )
    if large_files:
        risk_items.append(
            {
                "level": "medium",
                "item": "large files",
                "recommendation": "确认大文件是否适合 GitHub 仓库。",
                "files": large_files,
            }
        )
    for pattern, covered in key_gitignore_checks.items():
        if not covered:
            risk_items.append(
                {
                    "level": "medium",
                    "item": f".gitignore missing {pattern}",
                    "recommendation": "补充 .gitignore，避免敏感或缓存文件被提交。",
                }
            )

    return {
        "checked_at": datetime.now().replace(microsecond=0).isoformat(),
        "env_exists": env_exists,
        "tracked_file_count": len(tracked_files),
        "local_only_safe": local_only_safe,
        "tracked_risk": tracked_risk,
        "ignore_rule_missing": ignore_rule_missing,
        "possible_secret_findings": sensitive_findings,
        "log_files": log_files,
        "pycache_directories": pycache_dirs,
        "eval_results_sensitive_findings": eval_sensitive_findings,
        "orders_db_exists": (PROJECT_ROOT / "data" / "orders.db").exists(),
        "policy_faiss_index_exists": (PROJECT_ROOT / "data" / "indexes" / "policy_faiss.index").exists(),
        "large_files": large_files,
        "gitignore_coverage": key_gitignore_checks,
        "risk_items": risk_items,
        "passed": not risk_items,
        "boundary": "本脚本只检查，不删除文件、不读取 .env 内容、不执行 GitHub 操作。",
    }


def write_outputs(report: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# GitHub 发布前检查报告",
        "",
        f"- 检查时间：{report['checked_at']}",
        f"- 是否通过高风险检查：{report['passed']}",
        f"- 是否存在 .env：{report['env_exists']}",
        f"- 是否存在 orders.db：{report['orders_db_exists']}",
        f"- 是否存在 policy_faiss.index：{report['policy_faiss_index_exists']}",
        f"- 本地安全忽略项数量：{len(report['local_only_safe'])}",
        f"- 已跟踪风险项数量：{len(report['tracked_risk'])}",
        f"- 缺失忽略规则项数量：{len(report['ignore_rule_missing'])}",
        "",
        "## local_only_safe",
        "",
    ]
    if report["local_only_safe"]:
        for item in report["local_only_safe"]:
            lines.append(f"- `{item['path']}`：{item['recommendation']}")
    else:
        lines.append("- 无。")

    lines.extend(
        [
            "",
            "## tracked_risk",
            "",
        ]
    )
    if report["tracked_risk"]:
        for item in report["tracked_risk"]:
            lines.append(f"- `{item['path']}`：{item['recommendation']}")
    else:
        lines.append("- 无。")

    lines.extend(
        [
            "",
            "## ignore_rule_missing",
            "",
        ]
    )
    if report["ignore_rule_missing"]:
        for item in report["ignore_rule_missing"]:
            lines.append(f"- `{item['path']}`：{item['recommendation']}")
    else:
        lines.append("- 无。")

    lines.extend(
        [
            "",
            "## 失败风险项",
            "",
        ]
    )
    if report["risk_items"]:
        for item in report["risk_items"]:
            lines.append(f"- [{item['level']}] {item['item']}：{item['recommendation']}")
    else:
        lines.append("- 未发现会阻断发布的风险项。")

    lines.extend(
        [
            "",
            "## .gitignore 覆盖情况",
            "",
        ]
    )
    for pattern, covered in report["gitignore_coverage"].items():
        lines.append(f"- `{pattern}`：{covered}")

    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- 本脚本不会读取或打印 `.env` 内容。",
            "- 疑似密钥检查只报告文件路径和规则，不输出命中的敏感文本。",
            "- 发现风险不代表一定不能发布，但需要人工确认处理策略。",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    report = build_report()
    write_outputs(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
