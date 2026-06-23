"""
【文件作用】
本文件是项目中的 Python 模块，用于支撑当前目录对应的 Agent、RAG、Tool、API 或工程化能力。

【在项目中的位置】
它会被项目内的服务、脚本或测试按需导入。请结合文件名和所在目录理解具体调用关系。

【主要输入与输出】
输入和输出取决于具体函数。本注释只解释阅读路径，不改变业务逻辑、数据库、LLM 或 API 行为。
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# 直接运行 python scripts\init_demo_data.py 时，Python 默认从 scripts 目录开始找模块。
# 为了能稳定导入项目根目录下的 app.config，这里先把项目根目录加入导入路径。
PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from app.config import DEMO_REFERENCE_DATETIME


def get_project_root() -> Path:
    """
    获取项目根目录的绝对路径。

    参数：
        无。

    返回：
        Path：项目根目录路径，也就是 ecommerce_after_sales_agent 目录。

    用途：
        让脚本无论从哪个工作目录运行，都能稳定找到 data/orders.db。
    """
    # __file__ 表示当前 Python 文件的位置，也就是 scripts/init_demo_data.py。
    # parent 表示上一层目录：scripts。
    # 再 parent 一次，就能回到项目根目录 ecommerce_after_sales_agent。
    # 使用 resolve() 可以得到绝对路径，避免相对路径受当前命令行位置影响。
    project_root = Path(__file__).resolve().parent.parent
    return project_root


def get_database_path() -> Path:
    """
    获取模拟订单数据库文件路径。

    参数：
        无。

    返回：
        Path：data/orders.db 的绝对路径。

    用途：
        初始化脚本通过这个路径创建 SQLite 数据库文件。
    """
    project_root = get_project_root()
    database_path = project_root / "data" / "orders.db"
    return database_path


def format_datetime(datetime_value: datetime | None) -> str | None:
    """
    把 datetime 对象转换成适合写入 SQLite 的字符串。

    参数：
        datetime_value：需要转换的时间；如果没有签收时间，可以传 None。

    返回：
        str | None：格式化后的时间字符串，或 None。

    用途：
        SQLite 没有强制的 datetime 类型，本项目用文本保存时间，便于初学者查看。
    """
    if datetime_value is None:
        return None
    return datetime_value.strftime("%Y-%m-%d %H:%M:%S")


def build_demo_orders() -> list[tuple[Any, ...]]:
    """
    构造 12 条固定订单号的模拟订单数据。

    参数：
        无。

    返回：
        list[tuple[Any, ...]]：可直接批量写入 orders 表的订单元组列表。

    用途：
        把典型售后业务场景集中放在一个函数里，方便以后继续扩展。
    """
    # 使用固定模拟业务时间倒推订单时间和签收时间。
    # 不能直接依赖系统当前时间，否则过几天再运行测试时，
    # "签收 3 天"、"签收 10 天" 等场景会变成别的天数，测试就不稳定。
    reference_datetime = DEMO_REFERENCE_DATETIME

    # is_opened = 0 表示未拆封，1 表示已拆封。
    # has_quality_issue = 0 表示未报告质量问题，1 表示存在质量问题。
    demo_orders = [
        (
            "ORD10001",
            "USER001",
            "智选商城待付款保温杯",
            89.0,
            "unpaid",
            "unshipped",
            format_datetime(reference_datetime - timedelta(hours=2)),
            None,
            "none",
            0,
            0,
        ),
        (
            "ORD10002",
            "USER002",
            "智选商城家用电动牙刷",
            199.0,
            "paid",
            "unshipped",
            format_datetime(reference_datetime - timedelta(hours=10)),
            None,
            "none",
            0,
            0,
        ),
        (
            "ORD10003",
            "USER003",
            "智选蓝牙耳机",
            299.0,
            "paid",
            "shipped",
            format_datetime(reference_datetime - timedelta(days=2)),
            None,
            "none",
            0,
            0,
        ),
        (
            "ORD10004",
            "USER004",
            "智选商城旅行背包",
            159.0,
            "paid",
            "delivered",
            format_datetime(reference_datetime - timedelta(days=6)),
            format_datetime(reference_datetime - timedelta(days=3)),
            "none",
            0,
            0,
        ),
        (
            "ORD10005",
            "USER005",
            "智选商城厨房置物架",
            129.0,
            "paid",
            "delivered",
            format_datetime(reference_datetime - timedelta(days=13)),
            format_datetime(reference_datetime - timedelta(days=10)),
            "none",
            0,
            0,
        ),
        (
            "ORD10006",
            "USER006",
            "智选商城运动水杯",
            69.0,
            "paid",
            "delivered",
            format_datetime(reference_datetime - timedelta(days=5)),
            format_datetime(reference_datetime - timedelta(days=2)),
            "none",
            1,
            0,
        ),
        (
            "ORD10007",
            "USER007",
            "智选商城智能台灯",
            239.0,
            "paid",
            "delivered",
            format_datetime(reference_datetime - timedelta(days=13)),
            format_datetime(reference_datetime - timedelta(days=10)),
            "none",
            1,
            1,
        ),
        (
            "ORD10008",
            "USER008",
            "智选商城空气炸锅",
            399.0,
            "paid",
            "delivered",
            format_datetime(reference_datetime - timedelta(days=8)),
            format_datetime(reference_datetime - timedelta(days=5)),
            "refunded",
            0,
            0,
        ),
        (
            "ORD10009",
            "USER009",
            "智选商城床品四件套",
            269.0,
            "paid",
            "unshipped",
            format_datetime(reference_datetime - timedelta(days=1)),
            None,
            "cancelled",
            0,
            0,
        ),
        (
            "ORD10010",
            "USER010",
            "智选商城智能音箱",
            329.0,
            "paid",
            "delivered",
            format_datetime(reference_datetime - timedelta(days=22)),
            format_datetime(reference_datetime - timedelta(days=18)),
            "none",
            1,
            1,
        ),
        (
            "ORD10011",
            "USER011",
            "智选商城数码相机",
            2599.0,
            "paid",
            "unshipped",
            format_datetime(reference_datetime - timedelta(hours=20)),
            None,
            "none",
            0,
            0,
        ),
        (
            "ORD10012",
            "USER012",
            "智选商城平板电脑",
            3199.0,
            "paid",
            "shipped",
            format_datetime(reference_datetime - timedelta(days=1, hours=6)),
            None,
            "none",
            0,
            0,
        ),
    ]
    return demo_orders


def initialize_database() -> Path:
    """
    初始化模拟订单数据库。

    参数：
        无。

    返回：
        Path：初始化完成后的数据库文件路径。

    用途：
        创建 orders 和 tickets 两张表，并写入固定模拟订单数据。
    """
    database_path = get_database_path()

    # 确保 data 目录存在。parents=True 表示如果上级目录不存在也一起创建。
    database_path.parent.mkdir(parents=True, exist_ok=True)

    # sqlite3.connect(...) 用来打开 SQLite 数据库连接。
    # 如果 data/orders.db 不存在，SQLite 会自动创建这个文件。
    database_connection = sqlite3.connect(database_path)

    try:
        database_cursor = database_connection.cursor()

        # 初始化脚本需要可以重复运行。
        # 每次先删除旧表，再重建表和写入固定数据，测试就不会受旧数据残留影响。
        database_cursor.execute("DROP TABLE IF EXISTS tickets")
        database_cursor.execute("DROP TABLE IF EXISTS orders")

        database_cursor.execute(
            """
            CREATE TABLE orders (
                order_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                amount REAL NOT NULL,
                payment_status TEXT NOT NULL,
                shipping_status TEXT NOT NULL,
                order_time TEXT NOT NULL,
                delivery_time TEXT,
                refund_status TEXT NOT NULL,
                is_opened INTEGER NOT NULL,
                has_quality_issue INTEGER NOT NULL
            )
            """
        )

        database_cursor.execute(
            """
            CREATE TABLE tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                issue_type TEXT NOT NULL,
                description TEXT NOT NULL,
                ticket_status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        demo_orders = build_demo_orders()

        # 使用 executemany 批量插入，避免为每条订单重复写一段相同 SQL。
        # 这里的问号是参数占位符，SQLite 会把订单数据安全地填进去。
        database_cursor.executemany(
            """
            INSERT INTO orders (
                order_id,
                user_id,
                product_name,
                amount,
                payment_status,
                shipping_status,
                order_time,
                delivery_time,
                refund_status,
                is_opened,
                has_quality_issue
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            demo_orders,
        )

        # commit 表示确认写入。没有 commit 的话，数据可能只停留在当前连接里。
        database_connection.commit()
    finally:
        # 数据库连接会占用文件资源，用完后主动关闭更清晰，也能避免 Windows 上文件被占用。
        database_connection.close()

    return database_path


if __name__ == "__main__":
    # 以下 print 只用于本地学习演示，方便直接运行脚本时观察结果。
    # 后续正式服务化时，应改为结构化日志，而不是把 print 当作正式日志方案。
    created_database_path = initialize_database()
    print("模拟数据库初始化完成")
    print("订单数量：12")
    print(f"数据库路径：{created_database_path}")
