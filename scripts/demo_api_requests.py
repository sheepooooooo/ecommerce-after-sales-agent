"""
【文件作用】
本文件是项目中的 Python 模块，用于支撑当前目录对应的 Agent、RAG、Tool、API 或工程化能力。

【在项目中的位置】
它会被项目内的服务、脚本或测试按需导入。请结合文件名和所在目录理解具体调用关系。

【主要输入与输出】
输入和输出取决于具体函数。本注释只解释阅读路径，不改变业务逻辑、数据库、LLM 或 API 行为。
"""

import json
import urllib.error
import urllib.request


API_BASE_URL = "http://127.0.0.1:8011"


def post_agent_run(payload: dict) -> dict:
    request = urllib.request.Request(
        f"{API_BASE_URL}/agent/run",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    print("API Demo：以下输出仅用于本地学习演示，不是正式客户端日志。")
    scenarios = [
        {"user_query": "ORD10003 现在是什么状态？"},
        {"user_query": "ORD10004 可以退款吗？"},
        {"user_query": "我想退款"},
        {"user_query": "请创建工单，订单号是 ORD10003"},
        {"user_query": "请创建工单，订单号是 ORD10003", "confirm_ticket_creation": True},
    ]

    for index, payload in enumerate(scenarios, start=1):
        print(f"\n场景 {index}: {payload['user_query']}")
        try:
            response = post_agent_run(payload)
        except urllib.error.URLError as error:
            print(f"请求失败，请确认 API 已运行在 {API_BASE_URL}。错误：{error}")
            return
        print(json.dumps(response, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
