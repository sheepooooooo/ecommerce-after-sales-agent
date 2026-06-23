"""
生成 Swagger / API 演示用请求样例。

本脚本只生成模拟请求 JSON，不包含真实 API Key，不调用接口。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "docs" / "resume_evidence"
OUTPUT_PATH = OUTPUT_DIR / "demo_requests.json"


def build_demo_payloads() -> dict:
    return {
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "base_url": "http://127.0.0.1:8011",
        "notes": [
            "所有订单号均为模拟订单。",
            "请求样例不包含 API Key。",
            "工单创建必须显式区分 confirm_ticket_creation=false 与 true。",
        ],
        "requests": [
            {
                "name": "健康检查",
                "method": "GET",
                "path": "/health",
                "body": None,
            },
            {
                "name": "ORD10003 现在是什么状态？",
                "method": "POST",
                "path": "/agent/run",
                "body": {
                    "user_query": "ORD10003 现在是什么状态？",
                    "confirm_ticket_creation": False,
                },
            },
            {
                "name": "ORD10004 可以退款吗？",
                "method": "POST",
                "path": "/agent/run",
                "body": {
                    "user_query": "ORD10004 可以退款吗？",
                    "confirm_ticket_creation": False,
                },
            },
            {
                "name": "我想退款",
                "method": "POST",
                "path": "/agent/run",
                "body": {
                    "user_query": "我想退款",
                    "confirm_ticket_creation": False,
                },
            },
            {
                "name": "创建工单但不确认",
                "method": "POST",
                "path": "/agent/run",
                "body": {
                    "user_query": "请创建工单，订单号是 ORD10003",
                    "confirm_ticket_creation": False,
                },
            },
            {
                "name": "创建工单并确认",
                "method": "POST",
                "path": "/agent/run",
                "body": {
                    "user_query": "请创建工单，订单号是 ORD10003",
                    "confirm_ticket_creation": True,
                },
            },
            {
                "name": "我的银行卡被重复扣款了",
                "method": "POST",
                "path": "/agent/run",
                "body": {
                    "user_query": "我的银行卡被重复扣款了",
                    "confirm_ticket_creation": False,
                },
            },
            {
                "name": "耳机保修多久？",
                "method": "POST",
                "path": "/agent/run",
                "body": {
                    "user_query": "耳机保修多久？",
                    "confirm_ticket_creation": False,
                },
            },
        ],
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payloads = build_demo_payloads()
    OUTPUT_PATH.write_text(json.dumps(payloads, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成演示请求：{OUTPUT_PATH}")


if __name__ == "__main__":
    main()
