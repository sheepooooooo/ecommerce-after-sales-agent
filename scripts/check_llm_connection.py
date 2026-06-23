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
import time
from pathlib import Path

PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from app.config import get_llm_config
from app.llm.deepseek_client import generate_policy_answer


if __name__ == "__main__":
    llm_config = get_llm_config(require_api_key=False)
    if not llm_config["api_key"]:
        print("未检测到 DEEPSEEK_API_KEY。")
        print("请复制 .env.example 为 .env，并填入自己的 DEEPSEEK_API_KEY。")
        print("安全提示：不要把真实 Key 写入代码、README、测试或日志。")
        raise SystemExit(0)

    messages = [
        {"role": "system", "content": "只输出 JSON object。"},
        {"role": "user", "content": '{"answer":"连接测试","cited_chunk_ids":[],"needs_human_review":false,"missing_information":[]}'},
    ]
    start_time = time.perf_counter()
    try:
        result = generate_policy_answer(messages)
        latency_ms = (time.perf_counter() - start_time) * 1000
        print(f"当前模型名称：{result['model']}")
        print("调用是否成功：True")
        print(f"响应是否可解析为 JSON：{isinstance(result['parsed'], dict)}")
        print(f"耗时：{latency_ms:.2f} ms")
        print(json.dumps(result["parsed"], ensure_ascii=False, indent=2))
    except Exception as error:
        print(f"当前模型名称：{llm_config['model']}")
        print("调用是否成功：False")
        print(f"错误信息：{error}")
        raise SystemExit(0)
