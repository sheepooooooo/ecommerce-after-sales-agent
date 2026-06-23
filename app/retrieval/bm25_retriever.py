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


import re
import logging
import warnings
from typing import Any

warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
)

import jieba
from rank_bm25 import BM25Okapi

from app.config import DEFAULT_POLICY_TOP_K, MAX_POLICY_TOP_K
from app.retrieval.policy_schema import PolicyChunk


jieba.setLogLevel(logging.WARNING)

STOP_WORDS = {
    "我",
    "想",
    "问",
    "一下",
    "请问",
    "怎么",
    "怎么办",
    "可以",
    "能",
    "吗",
    "呢",
    "会",
    "不会",
    "帮",
    "帮我",
    "写",
    "一首",
    "关于",
    "学习",
    "怎么",
    "的",
    "了",
    "和",
    "或",
    "以及",
    "今天",
    "现在",
}


def tokenize_text(text: str) -> list[str]:
    """
    将中文文本分词为 BM25 可用 token。

    参数：
        text：用户问题或政策 chunk 内容。

    返回：
        list[str]：过滤空白后的 token 列表。

    用途：
        BM25 依赖关键词匹配；中文需要先分词，英文状态词统一小写。
    """
    normalized_text = re.sub(r"\s+", " ", text.strip().lower())
    raw_token_list = jieba.lcut(normalized_text)
    token_list: list[str] = []

    for raw_token in raw_token_list:
        token = raw_token.strip()
        if not token:
            continue
        if re.fullmatch(r"[^\w\u4e00-\u9fff]+", token):
            continue
        if token in STOP_WORDS:
            continue
        # 不丢弃订单号、数字和英文状态词，因为政策和订单状态解释可能会用到它们。
        token_list.append(token)

    return token_list


class BM25PolicyRetriever:
    """
    基于 BM25Okapi 的政策检索器。

    BM25 只看关键词匹配和词频统计，不理解同义表达。
    当前把它作为可解释检索基线，后续再加入向量检索增强同义表达召回。
    """

    def __init__(self, policy_chunk_list: list[PolicyChunk]) -> None:
        """
        初始化 BM25 检索器。

        参数：
            policy_chunk_list：从索引加载的政策 chunk 列表。

        返回：
            None。

        用途：
            将政策 chunk 预先分词并构建 BM25 语料。
        """
        self.policy_chunk_list = policy_chunk_list
        self.tokenized_corpus = [
            tokenize_text(
                f"{policy_chunk.document_title} "
                f"{policy_chunk.section_title} "
                f"{policy_chunk.content}"
            )
            for policy_chunk in policy_chunk_list
        ]
        self.bm25_model = BM25Okapi(self.tokenized_corpus)

    def normalize_top_k(self, top_k: int) -> int:
        """
        规范化 top_k。

        参数：
            top_k：用户希望返回的结果数量。

        返回：
            int：限制在合理范围内的 top_k。

        用途：
            非法 top_k 不应导致程序崩溃，也不应一次返回过多片段。
        """
        if not isinstance(top_k, int) or top_k <= 0:
            return DEFAULT_POLICY_TOP_K
        return min(top_k, MAX_POLICY_TOP_K)

    def retrieve(self, query: str, top_k: int = DEFAULT_POLICY_TOP_K) -> list[dict[str, Any]]:
        """
        检索与用户问题相关的政策 chunk。

        参数：
            query：用户问题。
            top_k：最多返回的相关片段数量。

        返回：
            list[dict[str, Any]]：按 BM25 分数降序排列的检索结果。

        用途：
            提供政策检索基线结果，不负责生成自然语言答案。
        """
        if not isinstance(query, str) or not query.strip():
            return []

        actual_top_k = self.normalize_top_k(top_k)
        query_token_list = tokenize_text(query)
        if not query_token_list:
            return []

        score_list = self.bm25_model.get_scores(query_token_list)
        ranked_index_list = sorted(
            range(len(score_list)),
            key=lambda chunk_index: score_list[chunk_index],
            reverse=True,
        )

        retrieval_result_list: list[dict[str, Any]] = []
        for chunk_index in ranked_index_list:
            bm25_score = float(score_list[chunk_index])
            # 无关问题不能强行返回政策。BM25 分数为 0 表示没有关键词命中。
            if bm25_score <= 0:
                continue

            policy_chunk = self.policy_chunk_list[chunk_index]
            retrieval_result_list.append(
                {
                    "rank": len(retrieval_result_list) + 1,
                    "chunk_id": policy_chunk.chunk_id,
                    "source_file": policy_chunk.source_file,
                    "document_title": policy_chunk.document_title,
                    "section_title": policy_chunk.section_title,
                    "content": policy_chunk.content,
                    "bm25_score": round(bm25_score, 4),
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
