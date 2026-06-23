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

from app.agent.after_sales_agent_service import run_after_sales_agent
from scripts.init_demo_data import initialize_database


def main() -> None:
    initialize_database()
    print("售后 Agent Demo：以下 print 仅用于学习演示，不是正式日志。")
    print("工单演示：第 5 条未确认，因此不会创建；第 6 条传入确认后才创建。")

    scenarios = [
        ("耳机买了以后一般保修多长时间？", False),
        ("ORD10003 现在是什么状态？", False),
        ("ORD10004 可以直接退款吗？", False),
        ("我想退款。", False),
        ("请帮我创建售后工单，订单号是 ORD10003。", False),
        ("请帮我创建售后工单，订单号是 ORD10003。并确认创建。", True),
        ("我的银行卡被重复扣款了。", False),
        ("今天天气怎么样？", False),
    ]

    for index, (query, confirm) in enumerate(scenarios, start=1):
        print(f"\n场景 {index}: {query}")
        result = run_after_sales_agent(
            query,
            confirm_ticket_creation=confirm,
            request_id=f"demo-{index}",
        )
        print(
            json.dumps(
                {
                    "intent": result["intent"],
                    "tool_used": result["tool_used"],
                    "answer_status": result["answer_status"],
                    "answer": result["answer"],
                    "error": result["error"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if result["intent"] == "policy_qa" and result["answer_status"] == "tool_error":
            print("提示：政策问答可能需要先配置 .env 中的 DEEPSEEK_API_KEY。")


if __name__ == "__main__":
    main()
