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

import faiss

PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from app.config import EMBEDDING_MODEL_NAME, POLICY_INDEX_DIRECTORY
from app.retrieval.embedding_service import embed_text_list
from app.retrieval.policy_index_manager import (
    get_policy_index_paths,
    load_policy_chunks_from_index,
)
from app.retrieval.policy_schema import PolicyChunk


def get_vector_index_paths() -> dict[str, Path]:
    """
    获取向量索引相关文件路径。

    参数：
        无。

    返回：
        dict[str, Path]：包含 faiss_index_path 和 vector_manifest_path。

    用途：
        统一管理 FAISS 索引和向量 manifest 的保存位置。
    """
    return {
        "faiss_index_path": POLICY_INDEX_DIRECTORY / "policy_faiss.index",
        "vector_manifest_path": POLICY_INDEX_DIRECTORY / "policy_vector_manifest.json",
    }


def calculate_file_sha256(file_path: Path) -> str:
    """
    计算文件 sha256。

    参数：
        file_path：需要计算摘要的文件路径。

    返回：
        str：sha256 十六进制字符串。

    用途：
        记录 chunk 索引版本，判断向量索引是否需要重建。
    """
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def build_vector_index() -> dict[str, Any]:
    """
    构建 FAISS 向量索引。

    参数：
        无。

    返回：
        dict[str, Any]：向量 manifest 信息和文件路径。

    用途：
        将 policy_chunks.jsonl 中的文本编码为向量，并持久化 FAISS IndexFlatIP。
    """
    policy_chunk_list = load_policy_chunks_from_index()
    if not policy_chunk_list:
        raise ValueError("政策 chunk 列表为空，无法构建向量索引。")

    # FAISS index 只保存向量，不保存文本，因此它和 chunk 列表的顺序必须完全一致。
    # search 返回的 index id 会直接用来回查同位置的 PolicyChunk。
    chunk_text_list = [
        f"{policy_chunk.document_title}\n{policy_chunk.section_title}\n{policy_chunk.content}"
        for policy_chunk in policy_chunk_list
    ]
    embedding_array = embed_text_list(chunk_text_list)
    vector_dimension = int(embedding_array.shape[1])

    # 当前政策库只有约 40 个 chunk，使用精确搜索的 IndexFlatIP 足够简单、稳定、可解释。
    # 不提前引入 IVF、HNSW 等近似索引，避免学习项目过早复杂化。
    faiss_index = faiss.IndexFlatIP(vector_dimension)
    faiss_index.add(embedding_array)

    POLICY_INDEX_DIRECTORY.mkdir(parents=True, exist_ok=True)
    vector_paths = get_vector_index_paths()
    policy_index_paths = get_policy_index_paths()
    chunk_index_sha256 = calculate_file_sha256(policy_index_paths["chunks_path"])

    manifest = {
        "index_version": 1,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "embedding_model_name": EMBEDDING_MODEL_NAME,
        "chunk_count": len(policy_chunk_list),
        "vector_dimension": vector_dimension,
        "chunk_index_sha256": chunk_index_sha256,
        "faiss_index_file": vector_paths["faiss_index_path"].name,
    }

    temporary_index_path = vector_paths["faiss_index_path"].with_suffix(".index.tmp")
    faiss.write_index(faiss_index, str(temporary_index_path))
    temporary_index_path.replace(vector_paths["faiss_index_path"])

    temporary_manifest_path = vector_paths["vector_manifest_path"].with_suffix(".json.tmp")
    temporary_manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_manifest_path.replace(vector_paths["vector_manifest_path"])

    return {
        **manifest,
        "faiss_index_path": str(vector_paths["faiss_index_path"]),
        "vector_manifest_path": str(vector_paths["vector_manifest_path"]),
    }


def load_vector_index() -> tuple[faiss.Index, list[PolicyChunk], dict[str, Any]]:
    """
    加载并校验 FAISS 向量索引。

    参数：
        无。

    返回：
        tuple[faiss.Index, list[PolicyChunk], dict[str, Any]]：索引、chunk 列表和 manifest。

    用途：
        检索前确保向量索引和当前 chunk 索引仍然匹配。
    """
    vector_paths = get_vector_index_paths()
    policy_index_paths = get_policy_index_paths()

    if not vector_paths["faiss_index_path"].exists() or not vector_paths["vector_manifest_path"].exists():
        raise FileNotFoundError(
            "向量索引不存在，请先运行：python scripts\\build_vector_index.py"
        )

    policy_chunk_list = load_policy_chunks_from_index()
    vector_manifest = json.loads(
        vector_paths["vector_manifest_path"].read_text(encoding="utf-8")
    )
    current_chunk_sha256 = calculate_file_sha256(policy_index_paths["chunks_path"])

    if vector_manifest.get("embedding_model_name") != EMBEDDING_MODEL_NAME:
        raise RuntimeError(
            "向量索引使用的 Embedding 模型与当前配置不一致，"
            "请重新运行：python scripts\\build_vector_index.py"
        )
    if int(vector_manifest.get("chunk_count", -1)) != len(policy_chunk_list):
        raise RuntimeError(
            "向量索引 chunk 数量与当前 policy_chunks.jsonl 不一致，"
            "请重新运行：python scripts\\build_vector_index.py"
        )
    if vector_manifest.get("chunk_index_sha256") != current_chunk_sha256:
        raise RuntimeError(
            "policy_chunks.jsonl 已变化，旧向量索引可能失效，"
            "请重新运行：python scripts\\build_vector_index.py"
        )

    faiss_index = faiss.read_index(str(vector_paths["faiss_index_path"]))
    return faiss_index, policy_chunk_list, vector_manifest


def validate_vector_index() -> dict[str, Any]:
    """
    校验向量索引是否与当前 chunk 索引一致。

    参数：
        无。

    返回：
        dict[str, Any]：校验结果。

    用途：
        供测试和运维脚本快速确认索引是否可用。
    """
    faiss_index, policy_chunk_list, vector_manifest = load_vector_index()
    return {
        "valid": True,
        "chunk_count": len(policy_chunk_list),
        "faiss_ntotal": int(faiss_index.ntotal),
        "vector_dimension": int(vector_manifest["vector_dimension"]),
        "embedding_model_name": vector_manifest["embedding_model_name"],
    }

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
