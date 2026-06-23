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


import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "eval_results"
SUMMARY_PATH = RESULTS_DIR / "full_check_summary.json"
REPORT_PATH = RESULTS_DIR / "full_check_report.md"


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def run_step(name: str, command: list[str]) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    start_time = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    elapsed_seconds = round(time.perf_counter() - start_time, 2)
    output = completed.stdout or ""
    return {
        "name": name,
        "command": command,
        "passed": completed.returncode == 0,
        "elapsed_seconds": elapsed_seconds,
        "return_code": completed.returncode,
        "failure_summary": None if completed.returncode == 0 else output[-2000:],
    }


def build_report(summary: dict[str, Any]) -> str:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    lines = [
        "# 全量回归验收报告",
        "",
        f"- 验收时间：{summary['checked_at']}",
        f"- 总耗时：{summary['total_elapsed_seconds']} 秒",
        f"- 整体通过：{summary['passed']}",
        "",
        "## 各步骤通过情况",
        "",
    ]
    for step in summary["steps"]:
        lines.extend(
            [
                f"### {step['name']}",
                "",
                f"- 通过：{step['passed']}",
                f"- 耗时：{step['elapsed_seconds']} 秒",
                f"- 返回码：{step['return_code']}",
                f"- 失败摘要：{step['failure_summary']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 当前未覆盖内容",
            "",
            "- 不运行真实 LLM 验收，不消耗 DeepSeek API。",
            "- 不执行 Docker 镜像构建。",
            "- 不代表生产级发布验证。",
            "",
            "## 项目边界",
            "",
            "- 当前是本地单进程、模拟业务、面试展示级工程化系统。",
            "- 进程内 Semaphore 不是分布式限流。",
            "- 当前不包含数据库持久化、高可用、鉴权、监控平台或生产级安全体系。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    start_time = time.perf_counter()
    steps = [
        ("初始化模拟订单数据库", [sys.executable, "scripts\\init_demo_data.py"]),
        ("构建政策索引", [sys.executable, "scripts\\build_all_policy_indexes.py"]),
        ("运行全部 pytest", [sys.executable, "-m", "pytest", "-q"]),
        ("运行 API 验收", [sys.executable, "scripts\\run_api_checks.py"]),
        ("运行稳定性测试", [sys.executable, "scripts\\stability_test.py"]),
    ]

    results: list[dict[str, Any]] = []
    stopped_after_failure = False
    for name, command in steps:
        result = run_step(name, command)
        results.append(result)
        if not result["passed"]:
            stopped_after_failure = True
            break

    summary = {
        "checked_at": datetime.now().replace(microsecond=0).isoformat(),
        "passed": all(step["passed"] for step in results) and len(results) == len(steps),
        "stopped_after_failure": stopped_after_failure,
        "total_elapsed_seconds": round(time.perf_counter() - start_time, 2),
        "steps": results,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
