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


from typing import Any

from app.config import (
    DEFAULT_DENSE_RELEVANCE_THRESHOLD,
    DEFAULT_POLICY_RETRIEVAL_MODE,
    DEFAULT_POLICY_TOP_K,
)
from app.retrieval.bm25_retriever import BM25PolicyRetriever
from app.retrieval.faiss_policy_retriever import FAISSPolicyRetriever
from app.retrieval.hybrid_policy_retriever import HybridPolicyRetriever
from app.retrieval.policy_index_manager import load_policy_chunks_from_index
from app.retrieval.vector_index_manager import load_vector_index


VALID_RETRIEVAL_MODES = {"bm25", "dense", "hybrid"}


def get_bm25_retriever() -> BM25PolicyRetriever:
    """
    获取 BM25 检索器。

    参数：
        无。

    返回：
        BM25PolicyRetriever：基于 chunk 索引构建的关键词检索器。

    用途：
        提供精确术语和政策关键词检索能力。
    """
    policy_chunk_list = load_policy_chunks_from_index()
    return BM25PolicyRetriever(policy_chunk_list)


def get_dense_retriever() -> FAISSPolicyRetriever:
    """
    获取 FAISS Dense 检索器。

    参数：
        无。

    返回：
        FAISSPolicyRetriever：基于向量索引的语义检索器。

    用途：
        提供口语化表达和语义相近表达的召回能力。
    """
    faiss_index, policy_chunk_list, vector_manifest = load_vector_index()
    return FAISSPolicyRetriever(faiss_index, policy_chunk_list, vector_manifest)


def get_hybrid_retriever() -> HybridPolicyRetriever:
    """
    获取 RRF 混合检索器。

    参数：
        无。

    返回：
        HybridPolicyRetriever：BM25 + Dense 的融合检索器。

    用途：
        同时利用关键词和语义召回，不直接混合原始分数。
    """
    return HybridPolicyRetriever(
        bm25_retriever=get_bm25_retriever(),
        dense_retriever=get_dense_retriever(),
    )


def get_policy_retriever() -> BM25PolicyRetriever:
    """
    获取默认 BM25 检索器。

    参数：
        无。

    返回：
        BM25PolicyRetriever：BM25 检索器。

    用途：
        保留第三阶段 A 的内部辅助入口，避免已有代码无法导入。
    """
    return get_bm25_retriever()


def assess_policy_relevance(
    retrieval_mode: str,
    retrieved_chunk_list: list[dict[str, Any]],
) -> tuple[bool, str]:
    """
    判断检索结果是否足够相关。

    参数：
        retrieval_mode：检索模式，支持 bm25、dense、hybrid。
        retrieved_chunk_list：检索器返回的候选 chunk 列表。

    返回：
        tuple[bool, str]：是否相关，以及判断理由。

    用途：
        避免“只要有向量候选就认为相关”，尤其是天气、股票等无关问题。
    """
    if not retrieved_chunk_list:
        return False, "没有检索到任何候选政策片段。"

    top_result = retrieved_chunk_list[0]

    if retrieval_mode == "bm25":
        bm25_score = float(top_result.get("bm25_score") or 0.0)
        if bm25_score > 0:
            return True, f"BM25 Top1 分数为 {bm25_score:.4f}，存在关键词命中证据。"
        return False, "BM25 Top1 分数不大于 0，缺少关键词命中证据。"

    if retrieval_mode == "dense":
        dense_score = float(top_result.get("dense_score") or 0.0)
        if dense_score >= DEFAULT_DENSE_RELEVANCE_THRESHOLD:
            return True, (
                f"Dense Top1 分数为 {dense_score:.4f}，达到当前经验阈值 "
                f"{DEFAULT_DENSE_RELEVANCE_THRESHOLD:.2f}。"
            )
        return False, (
            f"Dense Top1 分数为 {dense_score:.4f}，低于当前经验阈值 "
            f"{DEFAULT_DENSE_RELEVANCE_THRESHOLD:.2f}。"
        )

    if retrieval_mode == "hybrid":
        bm25_score = top_result.get("bm25_score")
        dense_score = top_result.get("dense_score")
        if bm25_score is not None and float(bm25_score) > 0:
            return True, "Hybrid Top1 存在 BM25 正分，说明有关键词证据。"
        if dense_score is not None and float(dense_score) >= DEFAULT_DENSE_RELEVANCE_THRESHOLD:
            return True, (
                "Hybrid Top1 虽无 BM25 正分，但 Dense 分数达到经验阈值，"
                "存在较强语义证据。"
            )
        return False, "Hybrid Top1 缺少关键词证据，Dense 分数也未达到经验阈值。"

    return False, f"未知检索模式：{retrieval_mode}。"


def retrieve_policies(
    query: str,
    top_k: int = DEFAULT_POLICY_TOP_K,
    retrieval_mode: str = DEFAULT_POLICY_RETRIEVAL_MODE,
) -> dict[str, Any]:
    """
    使用指定模式检索政策片段。

    参数：
        query：用户问题。
        top_k：最多返回的政策片段数量。
        retrieval_mode：检索模式，支持 bm25、dense、hybrid。

    返回：
        dict[str, Any]：统一结构化检索结果。

    用途：
        提供政策检索层能力，不生成答案、不查询订单、不判断退款资格。
    """
    if retrieval_mode not in VALID_RETRIEVAL_MODES:
        return {
            "success": False,
            "query": query,
            "retrieval_method": retrieval_mode,
            "top_k": top_k,
            "retrieved_chunks": [],
            "has_relevant_policy": False,
            "relevance_reason": f"非法检索模式：{retrieval_mode}，请使用 bm25、dense 或 hybrid。",
            "message": "检索模式不合法。",
            "error": f"Unsupported retrieval_mode: {retrieval_mode}",
        }

    if not isinstance(query, str) or not query.strip():
        return {
            "success": True,
            "query": query,
            "retrieval_method": retrieval_mode,
            "top_k": top_k,
            "retrieved_chunks": [],
            "has_relevant_policy": False,
            "relevance_reason": "问题为空，无法判断政策相关性。",
            "message": "问题为空，无法检索政策；请补充具体售后问题。",
            "error": None,
        }

    if retrieval_mode == "bm25":
        retriever = get_bm25_retriever()
        retrieved_chunks = retriever.retrieve(query=query, top_k=top_k)
        retrieval_method = "bm25"
    elif retrieval_mode == "dense":
        retriever = get_dense_retriever()
        retrieved_chunks = retriever.retrieve(query=query, top_k=top_k)
        retrieval_method = "dense_faiss"
    else:
        retriever = get_hybrid_retriever()
        retrieved_chunks = retriever.retrieve(query=query, top_k=top_k)
        retrieval_method = "hybrid_rrf"

    has_relevant_policy, relevance_reason = assess_policy_relevance(
        retrieval_mode=retrieval_mode,
        retrieved_chunk_list=retrieved_chunks,
    )
    if has_relevant_policy:
        message = f"已检索到 {len(retrieved_chunks)} 条候选政策片段，并通过相关性判断。"
    else:
        message = "未检索到足够相关的政策内容，建议补充问题或转人工处理。"

    return {
        "success": True,
        "query": query,
        "retrieval_method": retrieval_method,
        "top_k": top_k,
        "retrieved_chunks": retrieved_chunks if has_relevant_policy else [],
        "has_relevant_policy": has_relevant_policy,
        "relevance_reason": relevance_reason,
        "message": message,
        "error": None,
    }

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
