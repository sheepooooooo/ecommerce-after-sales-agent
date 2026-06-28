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

from app.services.policy_qa_service import answer_policy_question
from app.services.error_taxonomy import classify_exception


def ask_policy_question(
    query: str,
    top_k: int = 3,
    retrieval_mode: str = "bm25",
) -> dict[str, Any]:
    """
    对外提供政策问答能力。

    参数：
        query：用户政策咨询问题。
        top_k：检索证据数量。
        retrieval_mode：检索模式，支持 bm25、dense、hybrid。

    返回：
        dict[str, Any]：PolicyQAResponse 的 JSON 可序列化字典。

    用途：
        后续 Agent 可调用该 Tool 获取带引用的政策回答。
    """
    try:
        return answer_policy_question(
            query=query,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
        )
    except Exception as error:
        return {
            "success": False,
            "query": query,
            "answer_status": "generation_error",
            "answer": "政策问答服务发生错误，暂时无法回答。",
            "retrieval_mode": retrieval_mode,
            "retrieved_chunks": [],
            "citations": [],
            "has_relevant_policy": False,
            "generation": None,
            "grounding_verification": {"passed": False, "reason": "未处理异常已被 Tool 捕获。"},
            "message": "政策问答失败。",
            "error": str(error),
            "debug": {"llm_called": False, "error_category": classify_exception(error), "retry_count": 0},
        }


if __name__ == "__main__":
    # 以下 print 仅用于本地学习演示，正式服务应使用结构化日志。
    demo_queries = [
        "耳机保修多久？",
        "我付款成功了，为什么订单还是待付款？",
        "商品已经发货，但我临时不想要了怎么办？",
        "退货后优惠券会退回来吗？",
        "ORD10004 可以直接退款吗？",
        "今天天气怎么样？",
    ]

    for demo_query in demo_queries:
        print(json.dumps(ask_policy_question(demo_query), ensure_ascii=False, indent=2))

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
