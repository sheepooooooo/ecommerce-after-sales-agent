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
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import POLICY_DIRECTORY
from app.retrieval.policy_index_manager import (
    build_policy_index,
    calculate_file_sha256,
    get_policy_index_paths,
)
from app.retrieval.vector_index_manager import (
    build_vector_index,
    get_vector_index_paths,
    validate_vector_index,
)
from app.tools.order_tool import get_database_path
from scripts.init_demo_data import initialize_database


def _load_json(path: Path) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    return json.loads(path.read_text(encoding="utf-8"))


def _policy_manifest_matches_current_files(manifest_path: Path) -> tuple[bool, list[str]]:
    """
    检查 policy_index_manifest.json 是否与当前 data/policies/*.md 一致。
    """
    warnings: list[str] = []
    if not manifest_path.exists():
        return False, ["政策 chunk manifest 缺失。"]

    manifest = _load_json(manifest_path)
    indexed_files = {
        item["file"]: item["sha256"]
        for item in manifest.get("source_files", [])
    }
    current_files = {}
    for policy_path in sorted(POLICY_DIRECTORY.glob("*.md")):
        if policy_path.read_text(encoding="utf-8").strip():
            current_files[policy_path.name] = calculate_file_sha256(policy_path)

    if indexed_files != current_files:
        warnings.append(
            "政策文件与现有索引 manifest 不一致。请手动运行："
            "python scripts\\build_all_policy_indexes.py"
        )
        return False, warnings
    return True, warnings


def bootstrap_runtime() -> dict[str, Any]:
    """
    确保运行前所需的模拟数据库和索引存在。

    数据库不存在时可以初始化，因为它是本项目的本地模拟订单库，服务启动没有它就无法
    完成订单查询和退款判断。数据库已存在时不能自动重置，因为其中可能已有本地演示时
    创建的模拟工单；静默重置会让服务重启变成破坏性操作。

    索引缺失时可以构建，因为没有索引时政策检索无法工作。首次构建 FAISS 向量索引可能
    需要联网下载 Embedding 模型，这是预期成本。若索引已经存在但 manifest 过期，则不在
    服务启动阶段静默重建，避免启动时出现不可预期的大耗时；改为给出清晰手动重建提示。
    """
    actions: list[str] = []
    warnings: list[str] = []
    success = True

    database_path = get_database_path()
    if database_path.exists():
        database_status = "existing"
    else:
        initialize_database()
        database_status = "created"
        actions.append("initialized_demo_database")

    policy_index_paths = get_policy_index_paths()
    vector_index_paths = get_vector_index_paths()
    required_index_paths = [
        policy_index_paths["chunks_path"],
        policy_index_paths["manifest_path"],
        vector_index_paths["faiss_index_path"],
        vector_index_paths["vector_manifest_path"],
    ]

    missing_index_paths = [path for path in required_index_paths if not path.exists()]
    if missing_index_paths:
        build_policy_index()
        build_vector_index()
        policy_index_status = "created"
        actions.append("built_policy_indexes")
    else:
        manifest_valid, manifest_warnings = _policy_manifest_matches_current_files(
            policy_index_paths["manifest_path"]
        )
        warnings.extend(manifest_warnings)
        if not manifest_valid:
            policy_index_status = "stale"
            success = False
        else:
            try:
                validate_vector_index()
                policy_index_status = "valid"
            except Exception as error:
                policy_index_status = "invalid"
                success = False
                warnings.append(
                    f"向量索引不可用：{error}。请手动运行："
                    "python scripts\\build_all_policy_indexes.py"
                )

    return {
        "success": success,
        "database_status": database_status,
        "policy_index_status": policy_index_status,
        "actions": actions,
        "warnings": warnings,
    }


if __name__ == "__main__":
    # 以下 print 仅用于本地学习演示，不是正式日志。
    print(json.dumps(bootstrap_runtime(), ensure_ascii=False, indent=2))

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
