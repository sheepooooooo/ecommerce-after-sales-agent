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

import faiss

from app.config import DEFAULT_DENSE_CANDIDATE_K, DEFAULT_POLICY_TOP_K, MAX_POLICY_TOP_K
from app.retrieval.embedding_service import embed_single_text
from app.retrieval.policy_schema import PolicyChunk


class FAISSPolicyRetriever:
    """
    基于 FAISS IndexFlatIP 的政策向量检索器。

    Dense score 表示向量相似度，不等于业务正确率。
    即使用户问题完全无关，FAISS 也可能返回“最相近”的 chunk。
    """

    def __init__(
        self,
        faiss_index: faiss.Index,
        policy_chunk_list: list[PolicyChunk],
        vector_manifest: dict[str, Any],
    ) -> None:
        """
        初始化 Dense 检索器。

        参数：
            faiss_index：已加载的 FAISS 索引。
            policy_chunk_list：与 FAISS 向量顺序一致的 chunk 列表。
            vector_manifest：向量索引 manifest。

        返回：
            None。

        用途：
            保存检索所需的索引、chunk 和索引元信息。
        """
        self.faiss_index = faiss_index
        self.policy_chunk_list = policy_chunk_list
        self.vector_manifest = vector_manifest

    def normalize_top_k(self, top_k: int) -> int:
        """
        规范化 top_k。

        参数：
            top_k：用户请求的返回数量。

        返回：
            int：安全范围内的返回数量。

        用途：
            非法 top_k 不应导致程序崩溃。
        """
        if not isinstance(top_k, int) or top_k <= 0:
            return DEFAULT_POLICY_TOP_K
        return min(top_k, MAX_POLICY_TOP_K)

    def normalize_candidate_k(self, candidate_k: int | None, top_k: int) -> int:
        """
        规范化候选数量。

        参数：
            candidate_k：候选召回数量。
            top_k：最终返回数量。

        返回：
            int：安全候选数量。

        用途：
            Dense 检索可先取较多候选，再由上层融合或裁剪。
        """
        if not isinstance(candidate_k, int) or candidate_k <= 0:
            candidate_k = DEFAULT_DENSE_CANDIDATE_K
        candidate_k = max(candidate_k, top_k)
        return min(candidate_k, len(self.policy_chunk_list))

    def retrieve(
        self,
        query: str,
        top_k: int = DEFAULT_POLICY_TOP_K,
        candidate_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        使用 FAISS 检索语义相近政策片段。

        参数：
            query：用户问题。
            top_k：最终返回数量。
            candidate_k：内部候选数量；为空时使用默认值。

        返回：
            list[dict[str, Any]]：Dense 检索结果。

        用途：
            提供语义召回候选，不负责判断是否真的相关。
        """
        if not isinstance(query, str) or not query.strip():
            return []

        actual_top_k = self.normalize_top_k(top_k)
        actual_candidate_k = self.normalize_candidate_k(candidate_k, actual_top_k)
        query_embedding = embed_single_text(query)
        dense_score_array, index_id_array = self.faiss_index.search(
            query_embedding,
            actual_candidate_k,
        )

        retrieval_result_list: list[dict[str, Any]] = []
        for dense_score, index_id in zip(dense_score_array[0], index_id_array[0]):
            if int(index_id) < 0:
                continue
            if int(index_id) >= len(self.policy_chunk_list):
                continue

            policy_chunk = self.policy_chunk_list[int(index_id)]
            retrieval_result_list.append(
                {
                    "rank": len(retrieval_result_list) + 1,
                    "chunk_id": policy_chunk.chunk_id,
                    "source_file": policy_chunk.source_file,
                    "document_title": policy_chunk.document_title,
                    "section_title": policy_chunk.section_title,
                    "content": policy_chunk.content,
                    "dense_score": round(float(dense_score), 4),
                }
            )
            if len(retrieval_result_list) >= actual_top_k:
                break

        return retrieval_result_list

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
