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

PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from app.config import DEFAULT_POLICY_RETRIEVAL_MODE, DEFAULT_POLICY_TOP_K
from app.retrieval.policy_retriever import retrieve_policies


def retrieve_policy(
    query: str,
    top_k: int = DEFAULT_POLICY_TOP_K,
    retrieval_mode: str = DEFAULT_POLICY_RETRIEVAL_MODE,
) -> dict[str, Any]:
    """
    检索与用户问题相关的模拟政策片段。

    参数：
        query：用户输入的问题。
        top_k：最多返回的政策片段数量。
        retrieval_mode：检索模式，支持 bm25、dense、hybrid。

    返回：
        dict[str, Any]：统一结构化检索结果。

    用途：
        给后续 Agent 提供政策检索 Tool，但当前不生成最终自然语言答案。
    """
    try:
        return retrieve_policies(
            query=query,
            top_k=top_k,
            retrieval_mode=retrieval_mode,
        )
    except FileNotFoundError as error:
        return {
            "success": False,
            "query": query,
            "retrieval_method": retrieval_mode,
            "top_k": top_k,
            "retrieved_chunks": [],
            "has_relevant_policy": False,
            "relevance_reason": "检索索引尚未构建或缺少必要文件。",
            "message": "政策索引尚未构建。",
            "error": str(error),
        }
    except RuntimeError as error:
        return {
            "success": False,
            "query": query,
            "retrieval_method": retrieval_mode,
            "top_k": top_k,
            "retrieved_chunks": [],
            "has_relevant_policy": False,
            "relevance_reason": "检索服务运行时错误。",
            "message": "政策检索失败，请检查索引、模型或依赖。",
            "error": str(error),
        }


if __name__ == "__main__":
    # 以下 print 只用于本地学习演示，方便观察三种检索模式的 JSON 输出。
    demo_queries = [
        "订单已经发货但我不想要了怎么办？",
        "包裹已经寄出了，我临时改变主意不想收了怎么处理？",
        "耳机保修多久？",
        "支付扣款成功但订单还是待付款怎么办？",
        "退货以后优惠券会退回来吗？",
        "我想问今天天气怎么样？",
    ]

    for demo_query in demo_queries:
        for mode in ["bm25", "dense", "hybrid"]:
            print(json.dumps(retrieve_policy(demo_query, retrieval_mode=mode), ensure_ascii=False, indent=2))

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
