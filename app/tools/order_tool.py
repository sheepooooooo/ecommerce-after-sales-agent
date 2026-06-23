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


import sqlite3
from datetime import datetime
from pathlib import Path
from pprint import pprint
from typing import Any


def get_database_path() -> Path:
    """
    返回 data/orders.db 的绝对路径。

    参数：
        无。

    返回：
        Path：模拟订单数据库文件的绝对路径。

    用途：
        让订单 Tool 无论从哪个工作目录运行，都能找到同一个数据库文件。
    """
    # __file__ 表示当前文件 app/tools/order_tool.py 的位置。
    # parent 第一次回到 app/tools，第二次回到 app，第三次回到项目根目录。
    # 这样做不依赖命令行当前在哪个目录，直接运行本文件也能正确定位数据库。
    project_root = Path(__file__).resolve().parent.parent.parent
    database_path = project_root / "data" / "orders.db"
    return database_path


def ensure_database_exists(database_path: Path) -> None:
    """
    检查数据库文件是否已经存在。

    参数：
        database_path：需要检查的数据库路径。

    返回：
        None：如果数据库存在则不返回额外数据。

    用途：
        在查询或创建工单前给出清楚提示，避免用户看到难懂的 SQLite 报错。
    """
    if not database_path.exists():
        raise FileNotFoundError(
            "未找到模拟订单数据库 data/orders.db。"
            "请先运行：python scripts\\init_demo_data.py"
        )


def open_database_connection() -> sqlite3.Connection:
    """
    打开 SQLite 数据库连接。

    参数：
        无。

    返回：
        sqlite3.Connection：已经配置好 row_factory 的数据库连接。

    用途：
        统一创建数据库连接，减少重复代码。
    """
    database_path = get_database_path()
    ensure_database_exists(database_path)

    # sqlite3.connect(...) 用于连接本地 SQLite 数据库文件。
    # SQLite 适合当前学习阶段，因为它不需要单独安装数据库服务。
    database_connection = sqlite3.connect(database_path)

    # row_factory = sqlite3.Row 可以让查询结果像字典一样按字段名读取。
    # 这样比使用数字下标更清晰，例如 order_record["order_id"] 更容易理解。
    database_connection.row_factory = sqlite3.Row
    return database_connection


def convert_order_record_to_dict(order_record: sqlite3.Row) -> dict[str, Any]:
    """
    把 SQLite 订单记录转换成普通 Python 字典。

    参数：
        order_record：从 orders 表查询出来的一行记录。

    返回：
        dict[str, Any]：JSON 可序列化的订单字典。

    用途：
        把数据库内部格式转换成后续 Tool Calling 更容易使用的数据格式。
    """
    order_dict = dict(order_record)

    # SQLite 没有真正的布尔字段，本项目用 0/1 存储。
    # 转成 Python 的 False/True 后，Agent 或测试读取时语义更清楚，也能被 JSON 正常序列化。
    order_dict["is_opened"] = bool(order_dict["is_opened"])
    order_dict["has_quality_issue"] = bool(order_dict["has_quality_issue"])
    return order_dict


def get_order(order_id: str) -> dict[str, Any] | None:
    """
    查询指定订单。

    参数：
        order_id：订单号，例如 "ORD10003"。

    返回：
        dict[str, Any] | None：找到订单时返回普通字典；找不到时返回 None。

    用途：
        给后续 Agent 提供基础订单查询能力。
    """
    if not order_id or not order_id.strip():
        raise ValueError("order_id 不能为空，请传入有效订单号，例如 ORD10003。")

    database_connection = open_database_connection()

    try:
        database_cursor = database_connection.cursor()

        # 查询用户输入的订单号时，必须使用参数化 SQL。
        # 如果直接拼接字符串，恶意输入可能改变 SQL 语义，造成 SQL 注入风险。
        # 问号占位符会让 sqlite3 把 order_id 当作普通参数处理，而不是 SQL 代码。
        database_cursor.execute(
            """
            SELECT
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
            FROM orders
            WHERE order_id = ?
            """,
            (order_id.strip(),),
        )
        order_record = database_cursor.fetchone()

        if order_record is None:
            return None
        return convert_order_record_to_dict(order_record)
    finally:
        # 数据库连接用完后关闭，可以释放文件句柄，避免长期占用 orders.db。
        database_connection.close()


def convert_ticket_record_to_dict(ticket_record: sqlite3.Row) -> dict[str, Any]:
    """
    把 SQLite 工单记录转换成普通 Python 字典。

    参数：
        ticket_record：从 tickets 表查询出来的一行记录。

    返回：
        dict[str, Any]：JSON 可序列化的工单字典。

    用途：
        让 create_ticket 和 list_tickets 返回一致的数据结构。
    """
    ticket_dict = dict(ticket_record)
    return ticket_dict


def create_ticket(
    order_id: str | None,
    issue_type: str,
    description: str,
) -> dict[str, Any]:
    """
    创建一条模拟售后工单。

    参数：
        order_id：关联订单号；如果问题暂时无法关联订单，可传 None。
        issue_type：问题类型，例如 "refund_dispute" 或 "warranty_request"。
        description：用户问题描述。

    返回：
        dict[str, Any]：创建后的工单信息。

    用途：
        当规则无法直接判断时，把问题记录为人工客服可处理的工单。
    """
    if not issue_type or not issue_type.strip():
        raise ValueError("issue_type 不能为空，请填写清楚的问题类型。")
    if not description or not description.strip():
        raise ValueError("description 不能为空，请填写用户问题描述。")

    cleaned_order_id = order_id.strip() if order_id and order_id.strip() else None
    cleaned_issue_type = issue_type.strip()
    cleaned_description = description.strip()
    created_at = datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    ticket_status = "open"

    database_connection = open_database_connection()

    try:
        database_cursor = database_connection.cursor()

        # 投诉、保修争议、物流异常或无法规则化判断的问题，通常需要转人工。
        # 工单可以保存用户描述和处理状态，让人工客服后续继续跟进。
        database_cursor.execute(
            """
            INSERT INTO tickets (
                order_id,
                issue_type,
                description,
                ticket_status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cleaned_order_id,
                cleaned_issue_type,
                cleaned_description,
                ticket_status,
                created_at,
            ),
        )
        ticket_id = database_cursor.lastrowid
        database_connection.commit()

        database_cursor.execute(
            """
            SELECT
                ticket_id,
                order_id,
                issue_type,
                description,
                ticket_status,
                created_at
            FROM tickets
            WHERE ticket_id = ?
            """,
            (ticket_id,),
        )
        ticket_record = database_cursor.fetchone()

        if ticket_record is None:
            raise RuntimeError("工单创建后未能读取到记录，请检查 tickets 表是否正常。")
        return convert_ticket_record_to_dict(ticket_record)
    finally:
        # 主动关闭连接，确保数据写入完成后释放数据库文件。
        database_connection.close()


def list_tickets(order_id: str | None = None) -> list[dict[str, Any]]:
    """
    查询模拟售后工单列表。

    参数：
        order_id：可选订单号；传入时只查询该订单下的工单，不传时查询全部工单。

    返回：
        list[dict[str, Any]]：按 ticket_id 倒序排列的工单列表。

    用途：
        方便调试，也方便后续测试检查工单是否已经创建。
    """
    database_connection = open_database_connection()

    try:
        database_cursor = database_connection.cursor()

        if order_id and order_id.strip():
            # 这里同样使用参数化查询，避免把用户输入直接拼进 SQL 字符串。
            database_cursor.execute(
                """
                SELECT
                    ticket_id,
                    order_id,
                    issue_type,
                    description,
                    ticket_status,
                    created_at
                FROM tickets
                WHERE order_id = ?
                ORDER BY ticket_id DESC
                """,
                (order_id.strip(),),
            )
        else:
            database_cursor.execute(
                """
                SELECT
                    ticket_id,
                    order_id,
                    issue_type,
                    description,
                    ticket_status,
                    created_at
                FROM tickets
                ORDER BY ticket_id DESC
                """
            )

        ticket_records = database_cursor.fetchall()
        ticket_dicts = [
            convert_ticket_record_to_dict(ticket_record)
            for ticket_record in ticket_records
        ]
        return ticket_dicts
    finally:
        database_connection.close()


if __name__ == "__main__":
    # 以下 print / pprint 只用于本地学习演示，方便直接运行 Tool 文件观察结果。
    # 后续正式服务化时，应改为结构化日志和工具调用轨迹记录。
    print("演示：查询订单 ORD10003")
    pprint(get_order("ORD10003"), sort_dicts=False)

    print("\n演示：创建一条模拟售后工单")
    created_ticket = create_ticket(
        order_id="ORD10003",
        issue_type="refund_dispute",
        description="用户表示商品存在异常，希望人工客服进一步处理。",
    )
    pprint(created_ticket, sort_dicts=False)

    print("\n演示：查询 ORD10003 下的工单")
    pprint(list_tickets("ORD10003"), sort_dicts=False)

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
