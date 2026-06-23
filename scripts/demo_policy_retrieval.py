"""
【文件作用】
本文件是项目中的 Python 模块，用于支撑当前目录对应的 Agent、RAG、Tool、API 或工程化能力。

【在项目中的位置】
它会被项目内的服务、脚本或测试按需导入。请结合文件名和所在目录理解具体调用关系。

【主要输入与输出】
输入和输出取决于具体函数。本注释只解释阅读路径，不改变业务逻辑、数据库、LLM 或 API 行为。
"""

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from app.tools.policy_retrieval_tool import retrieve_policy


def extract_score_info(retrieved_chunk: dict[str, Any] | None) -> dict[str, Any]:
    """
    提取 Top1 分数信息。

    参数：
        retrieved_chunk：Top1 检索结果，可能为空。

    返回：
        dict[str, Any]：包含 BM25、Dense、RRF 分数的简要字典。

    用途：
        让演示输出更短，更容易看三种模式差异。
    """
    if retrieved_chunk is None:
        return {}
    return {
        "bm25_score": retrieved_chunk.get("bm25_score"),
        "dense_score": retrieved_chunk.get("dense_score"),
        "rrf_score": retrieved_chunk.get("rrf_score"),
    }


def print_mode_result(query: str, retrieval_mode: str) -> None:
    """
    打印某个问题在指定检索模式下的结果。

    参数：
        query：演示问题。
        retrieval_mode：检索模式，支持 bm25、dense、hybrid。

    返回：
        None。

    用途：
        对比三种检索模式的 Top1 来源和相关性判断。
    """
    result = retrieve_policy(query=query, top_k=3, retrieval_mode=retrieval_mode)
    top1_chunk = result["retrieved_chunks"][0] if result["retrieved_chunks"] else None
    summary = {
        "检索模式": retrieval_mode,
        "has_relevant_policy": result["has_relevant_policy"],
        "relevance_reason": result["relevance_reason"],
        "Top1 文件": top1_chunk["source_file"] if top1_chunk else None,
        "Top1 小节": top1_chunk["section_title"] if top1_chunk else None,
        "分数信息": extract_score_info(top1_chunk),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    demo_queries = [
        "订单已经发货但我不想要了怎么办？",
        "包裹已经寄出了，我临时改变主意不想收了怎么处理？",
        "耳机保修多久？",
        "支付扣款成功但订单还是待付款怎么办？",
        "退货以后优惠券会退回来吗？",
        "我想问今天天气怎么样？",
    ]

    for demo_query in demo_queries:
        print("=" * 80)
        print(f"问题：{demo_query}")
        for mode in ["bm25", "dense", "hybrid"]:
            print_mode_result(demo_query, mode)
