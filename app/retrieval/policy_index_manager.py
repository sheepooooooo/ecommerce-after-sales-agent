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


import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from app.config import POLICY_DIRECTORY, POLICY_INDEX_DIRECTORY
from app.retrieval.policy_loader import build_all_policy_chunks, load_policy_documents
from app.retrieval.policy_schema import PolicyChunk


def get_policy_index_paths() -> dict[str, Path]:
    """
    获取政策索引相关文件路径。

    参数：
        无。

    返回：
        dict[str, Path]：包含 chunks_path 和 manifest_path。

    用途：
        统一管理索引文件位置，避免脚本和服务各自拼路径。
    """
    return {
        "chunks_path": POLICY_INDEX_DIRECTORY / "policy_chunks.jsonl",
        "manifest_path": POLICY_INDEX_DIRECTORY / "policy_index_manifest.json",
    }


def calculate_file_sha256(policy_document_path: Path) -> str:
    """
    计算政策文件的 sha256 摘要。

    参数：
        policy_document_path：政策 Markdown 文件路径。

    返回：
        str：文件内容的 sha256 十六进制字符串。

    用途：
        manifest 保存摘要后，后续可以判断政策是否变化、索引是否需要重建。
    """
    file_bytes = policy_document_path.read_bytes()
    return hashlib.sha256(file_bytes).hexdigest()


def write_jsonl_atomically(jsonl_path: Path, policy_chunk_list: list[PolicyChunk]) -> None:
    """
    原子化写入 JSONL chunk 文件。

    参数：
        jsonl_path：目标 JSONL 路径。
        policy_chunk_list：待保存的 chunk 列表。

    返回：
        None。

    用途：
        先写临时文件再 replace，避免写入中断时留下半个索引文件。
    """
    temporary_path = jsonl_path.with_suffix(".jsonl.tmp")
    with temporary_path.open("w", encoding="utf-8") as output_file:
        for policy_chunk in policy_chunk_list:
            output_file.write(
                json.dumps(policy_chunk.to_dict(), ensure_ascii=False) + "\n"
            )
    temporary_path.replace(jsonl_path)


def write_manifest_atomically(manifest_path: Path, manifest: dict[str, Any]) -> None:
    """
    原子化写入索引 manifest。

    参数：
        manifest_path：目标 manifest 路径。
        manifest：索引元信息。

    返回：
        None。

    用途：
        manifest 帮助后续排查索引版本、来源文件和 chunk 数量问题。
    """
    temporary_path = manifest_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(manifest_path)


def build_policy_index() -> dict[str, Any]:
    """
    构建本地政策索引。

    参数：
        无。

    返回：
        dict[str, Any]：manifest 内容和索引文件路径。

    用途：
        将政策 Markdown 转为 JSONL chunk 索引，供在线检索服务快速加载。
    """
    # 政策文档变化后必须重新构建索引，否则检索服务仍会读取旧 chunk。
    # 构建索引和在线检索分离，可以让运行时检索更稳定，也方便离线评测。
    policy_document_list = load_policy_documents()
    policy_chunk_list = build_all_policy_chunks()
    index_paths = get_policy_index_paths()
    POLICY_INDEX_DIRECTORY.mkdir(parents=True, exist_ok=True)

    source_files = []
    for policy_document_path in sorted(POLICY_DIRECTORY.glob("*.md")):
        if policy_document_path.read_text(encoding="utf-8").strip():
            source_files.append(
                {
                    "file": policy_document_path.name,
                    "sha256": calculate_file_sha256(policy_document_path),
                }
            )

    manifest = {
        "index_version": 1,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "document_count": len(policy_document_list),
        "chunk_count": len(policy_chunk_list),
        "source_files": source_files,
    }

    # JSONL 每行一个 chunk，人工打开时也能逐行查看，适合学习和调试。
    write_jsonl_atomically(index_paths["chunks_path"], policy_chunk_list)
    write_manifest_atomically(index_paths["manifest_path"], manifest)

    return {
        **manifest,
        "chunks_path": str(index_paths["chunks_path"]),
        "manifest_path": str(index_paths["manifest_path"]),
    }


def load_policy_chunks_from_index() -> list[PolicyChunk]:
    """
    从本地 JSONL 索引加载政策 chunk。

    参数：
        无。

    返回：
        list[PolicyChunk]：索引中的全部 chunk。

    用途：
        在线检索服务只加载已构建索引，不直接反复扫描 Markdown。
    """
    index_paths = get_policy_index_paths()
    chunks_path = index_paths["chunks_path"]

    if not chunks_path.exists():
        raise FileNotFoundError(
            "政策索引不存在，请先运行：python scripts\\build_policy_index.py"
        )

    policy_chunk_list: list[PolicyChunk] = []
    with chunks_path.open("r", encoding="utf-8") as input_file:
        for line_text in input_file:
            if line_text.strip():
                policy_chunk_list.append(
                    PolicyChunk.from_dict(json.loads(line_text))
                )

    return policy_chunk_list

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
