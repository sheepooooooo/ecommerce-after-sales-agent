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

from app.config import DEFAULT_HYBRID_CANDIDATE_K, DEFAULT_POLICY_TOP_K, MAX_POLICY_TOP_K, RRF_K
from app.retrieval.bm25_retriever import BM25PolicyRetriever
from app.retrieval.faiss_policy_retriever import FAISSPolicyRetriever


class HybridPolicyRetriever:
    """
    BM25 + Dense 的混合政策检索器。

    BM25 适合精确术语、订单状态和政策关键词。
    Dense Retrieval 适合口语化表达、同义表达和语义相近表达。
    RRF 用排名融合，避免直接混合不同量纲的原始分数。
    """

    def __init__(
        self,
        bm25_retriever: BM25PolicyRetriever,
        dense_retriever: FAISSPolicyRetriever,
    ) -> None:
        """
        初始化混合检索器。

        参数：
            bm25_retriever：BM25 检索器。
            dense_retriever：FAISS Dense 检索器。

        返回：
            None。

        用途：
            组合关键词检索和语义检索候选。
        """
        self.bm25_retriever = bm25_retriever
        self.dense_retriever = dense_retriever

    def normalize_top_k(self, top_k: int) -> int:
        """
        规范化 top_k。

        参数：
            top_k：用户请求的返回数量。

        返回：
            int：安全范围内的返回数量。

        用途：
            避免非法参数导致检索崩溃。
        """
        if not isinstance(top_k, int) or top_k <= 0:
            return DEFAULT_POLICY_TOP_K
        return min(top_k, MAX_POLICY_TOP_K)

    def normalize_candidate_k(self, candidate_k: int | None, top_k: int) -> int:
        """
        规范化融合候选数量。

        参数：
            candidate_k：每一路检索候选数量。
            top_k：最终返回数量。

        返回：
            int：安全候选数量。

        用途：
            RRF 需要每一路先召回一批候选，再按排名融合。
        """
        if not isinstance(candidate_k, int) or candidate_k <= 0:
            candidate_k = DEFAULT_HYBRID_CANDIDATE_K
        return max(candidate_k, top_k)

    def retrieve(
        self,
        query: str,
        top_k: int = DEFAULT_POLICY_TOP_K,
        candidate_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        执行混合政策检索。

        参数：
            query：用户问题。
            top_k：最终返回数量。
            candidate_k：每一路候选数量。

        返回：
            list[dict[str, Any]]：RRF 融合后的检索结果。

        用途：
            同时利用关键词命中和语义相似度，提高政策召回稳健性。
        """
        if not isinstance(query, str) or not query.strip():
            return []

        actual_top_k = self.normalize_top_k(top_k)
        actual_candidate_k = self.normalize_candidate_k(candidate_k, actual_top_k)
        bm25_results = self.bm25_retriever.retrieve(
            query=query,
            top_k=actual_candidate_k,
        )
        dense_results = self.dense_retriever.retrieve(
            query=query,
            top_k=actual_candidate_k,
            candidate_k=actual_candidate_k,
        )

        fused_result_map: dict[str, dict[str, Any]] = {}

        for bm25_result in bm25_results:
            chunk_id = bm25_result["chunk_id"]
            fused_result_map[chunk_id] = {
                **bm25_result,
                "rrf_score": 0.0,
                "bm25_score": bm25_result.get("bm25_score"),
                "bm25_rank": bm25_result.get("rank"),
                "dense_score": None,
                "dense_rank": None,
            }
            fused_result_map[chunk_id]["rrf_score"] += 1 / (
                RRF_K + int(bm25_result["rank"])
            )

        for dense_result in dense_results:
            chunk_id = dense_result["chunk_id"]
            if chunk_id not in fused_result_map:
                fused_result_map[chunk_id] = {
                    **dense_result,
                    "rrf_score": 0.0,
                    "bm25_score": None,
                    "bm25_rank": None,
                    "dense_score": dense_result.get("dense_score"),
                    "dense_rank": dense_result.get("rank"),
                }
            else:
                fused_result_map[chunk_id]["dense_score"] = dense_result.get("dense_score")
                fused_result_map[chunk_id]["dense_rank"] = dense_result.get("rank")
            fused_result_map[chunk_id]["rrf_score"] += 1 / (
                RRF_K + int(dense_result["rank"])
            )

        sorted_results = sorted(
            fused_result_map.values(),
            key=lambda result: (
                -float(result["rrf_score"]),
                -(float(result["dense_score"]) if result["dense_score"] is not None else -1.0),
                str(result["chunk_id"]),
            ),
        )

        final_results: list[dict[str, Any]] = []
        for result in sorted_results[:actual_top_k]:
            result["rank"] = len(final_results) + 1
            result["rrf_score"] = round(float(result["rrf_score"]), 6)
            final_results.append(result)

        return final_results

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
