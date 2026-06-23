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
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT, get_api_config


LOGGER_NAME = "ecommerce_after_sales_agent.api"
LOG_PATH = PROJECT_ROOT / "logs" / "agent_api.log"


class JsonLineFormatter(logging.Formatter):
    """
    把 dict 日志消息格式化成单行 JSON。
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        本函数是当前模块的辅助或核心步骤。
        
        参数：
            见函数签名。
        
        返回：
            见调用方使用的结构化结果。
        
        副作用：
            不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
        """
        payload: dict[str, Any]
        if isinstance(record.msg, dict):
            payload = dict(record.msg)
        else:
            payload = {"event": str(record.getMessage())}

        payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        payload.setdefault("level", record.levelname)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> logging.Logger:
    """
    幂等初始化 API 日志。
    """
    api_config = get_api_config()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(getattr(logging, api_config["log_level"], logging.INFO))
    logger.propagate = False

    existing_paths = {
        getattr(handler, "baseFilename", None)
        for handler in logger.handlers
        if isinstance(handler, RotatingFileHandler)
    }
    if str(LOG_PATH) not in existing_paths:
        handler = RotatingFileHandler(
            LOG_PATH,
            maxBytes=api_config["log_max_bytes"],
            backupCount=api_config["log_backup_count"],
            encoding="utf-8",
        )
        handler.setFormatter(JsonLineFormatter())
        logger.addHandler(handler)

    return logger


def get_api_logger() -> logging.Logger:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    return configure_logging()

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
