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

PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from app.tools.policy_qa_tool import ask_policy_question


if __name__ == "__main__":
    print("以下输出仅用于学习演示，正式服务应使用结构化日志。")
    demo_queries = [
        "耳机保修多久？",
        "我付款成功了，为什么订单还是待付款？",
        "商品已经发货，但我临时不想要了怎么办？",
        "退货后优惠券会退回来吗？",
        "ORD10004 可以直接退款吗？",
        "今天天气怎么样？",
    ]

    for demo_query in demo_queries:
        print("=" * 80)
        result = ask_policy_question(demo_query, retrieval_mode="bm25", top_k=3)
        print(json.dumps(result, ensure_ascii=False, indent=2))
